"""Chat session + message endpoints with SSE streaming (CHAT-04).

Five endpoints, all authed via `require_auth`:

- `POST   /api/chat/sessions`                  — create a new chat session for
  the caller's active portfolio.
- `GET    /api/chat/sessions`                  — list caller's sessions,
  newest first (messages omitted).
- `GET    /api/chat/sessions/{id}`             — fetch one session with its
  full message history.
- `DELETE /api/chat/sessions/{id}`             — remove a session; message
  rows cascade.
- `POST   /api/chat/sessions/{id}/messages`    — send a user message; response
  is a Server-Sent Events stream that emits the persisted assistant reply.

Cross-user isolation mirrors REL-06 / IMP-05 / BRIEF-04: every query scopes on
`chat_sessions.user_id == caller.user_id` and cross-user access returns 404
(never 403) so existence isn't leaked.

The turn runner (the coroutine that drives one user->assistant turn through
CHAT-03's `run_chat_turn`) is injected as a FastAPI dependency
(`get_chat_turn_runner`) so tests can substitute a fake that persists a canned
`ChatMessage` without booting Chroma / a live LLM.

Deviations from BUILD.md's event vocabulary (`token`, `tool_call`,
`tool_result`, `citations`, `done`):

    CHAT-03's `run_chat_turn` is currently a single awaitable that returns the
    finished, persisted assistant row — there is no per-token stream and no
    per-tool event stream today. The SSE endpoint therefore models the whole
    turn as:

        1. `token`     {"delta": "<full assembled content>"}   (one frame)
        2. `citations` [<serialized Citation>, ...]
        3. `done`      {"message_id": "<uuid>"}

    `tool_call` / `tool_result` events are omitted for now; a future CHAT-03
    refactor exposing LangGraph's `astream_events` will emit real per-token
    deltas and per-tool pairs. The wire contract above stays additive so
    clients written against CHAT-04 will keep working.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.graph import run_chat_turn
from app.db.base import get_db_session, get_session_factory
from app.db.models.chat import ChatMessage, ChatSession
from app.db.models.news import NewsCluster
from app.db.models.portfolio import Portfolio
from app.db.vectorstore import VectorStore
from app.schemas.chat import (
    ChatMessageIn,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionRead,
)
from app.utils.auth import UserContext, require_auth
from app.utils.embeddings import EmbeddingClient
from app.utils.llm import LLMClient

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# Type alias for the turn-runner callable. Tests override this via
# `app.dependency_overrides[get_chat_turn_runner]` so a fake runner can
# persist a canned assistant row without booting the CHAT-03 graph.
#
# Simplified from BUILD.md's suggested signature (which listed session / llm /
# news_store / embed as parameters): the default runner constructs its own
# request-independent session + clients since the FastAPI request-scoped
# session dies before the SSE generator finishes streaming.
TurnRunnerFn = Callable[[UUID, UUID, str], Awaitable[ChatMessage]]


async def _default_turn_runner(
    session_id: UUID, user_id: UUID, content: str
) -> ChatMessage:
    """Drive one chat turn end-to-end using a fresh AsyncSession."""
    session_factory = get_session_factory()
    llm = LLMClient()
    news_store = VectorStore("news_items")
    embed = EmbeddingClient()
    async with session_factory() as session:
        return await run_chat_turn(
            session_id,
            user_id,
            content,
            session=session,
            llm=llm,
            news_store=news_store,
            embed=embed,
        )


def get_chat_turn_runner() -> TurnRunnerFn:
    """FastAPI dependency — swap via `app.dependency_overrides` in tests."""
    return _default_turn_runner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _active_portfolio(user_id: UUID, db: AsyncSession) -> Portfolio | None:
    q = select(Portfolio).where(
        Portfolio.user_id == user_id, Portfolio.is_active.is_(True)
    )
    return (await db.execute(q)).scalar_one_or_none()


async def _get_owned_session(
    session_id: UUID, user_id: UUID, db: AsyncSession
) -> ChatSession:
    """Load a session scoped to the caller; 404 on miss (also for other users)."""
    row = (
        await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="chat session not found",
        )
    return row


def _sse_event(event: str, data: Any) -> bytes:
    """Encode one SSE frame — `event: <name>\\ndata: <json>\\n\\n` as UTF-8."""
    payload = data if isinstance(data, str) else json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


# ---------------------------------------------------------------------------
# POST /api/chat/sessions
# ---------------------------------------------------------------------------


@router.post(
    "/sessions",
    response_model=ChatSessionRead,
    status_code=status.HTTP_201_CREATED,
    name="create_chat_session",
)
async def create_chat_session(
    body: ChatSessionCreate,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> ChatSessionRead:
    portfolio = await _active_portfolio(user.user_id, db)
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active portfolio",
        )

    # Pre-check the seed cluster so we return a clear 400 (rather than a raw
    # FK error) when the client sent a stale/unknown cluster id.
    if body.seed_cluster_id is not None:
        exists = (
            await db.execute(
                select(NewsCluster.id).where(
                    NewsCluster.id == body.seed_cluster_id
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"seed_cluster_id {body.seed_cluster_id} does not exist",
            )

    row = ChatSession(
        user_id=user.user_id,
        portfolio_id=portfolio.id,
        title=body.title,
        seed_cluster_id=body.seed_cluster_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    # Fresh session — no messages yet. ChatSessionRead defaults messages=[].
    return ChatSessionRead.model_validate(row)


# ---------------------------------------------------------------------------
# GET /api/chat/sessions
# ---------------------------------------------------------------------------


@router.get(
    "/sessions",
    response_model=list[ChatSessionRead],
    name="list_chat_sessions",
)
async def list_chat_sessions(
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> list[ChatSessionRead]:
    rows = (
        await db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user.user_id)
            .order_by(ChatSession.updated_at.desc())
        )
    ).scalars().all()
    # Messages omitted deliberately — list view; a per-session message fetch
    # would be N+1 heavy. Clients call GET /sessions/{id} for the history.
    return [ChatSessionRead.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /api/chat/sessions/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionRead,
    name="get_chat_session",
)
async def get_chat_session(
    session_id: UUID,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> ChatSessionRead:
    row = await _get_owned_session(session_id, user.user_id, db)
    messages = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
    ).scalars().all()
    return ChatSessionRead.model_validate(row).model_copy(
        update={
            "messages": [ChatMessageRead.model_validate(m) for m in messages]
        }
    )


# ---------------------------------------------------------------------------
# DELETE /api/chat/sessions/{id}
# ---------------------------------------------------------------------------


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    name="delete_chat_session",
)
async def delete_chat_session(
    session_id: UUID,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    row = await _get_owned_session(session_id, user.user_id, db)
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# POST /api/chat/sessions/{id}/messages
# ---------------------------------------------------------------------------


async def _chat_sse_generator(
    session_id: UUID,
    user_id: UUID,
    content: str,
    runner: TurnRunnerFn,
) -> AsyncIterator[bytes]:
    """Yield SSE frames for one chat turn.

    Runs the turn to completion (CHAT-03 today is single-await, not a streaming
    graph — see module docstring for the deviation), then emits a synthetic
    `token` frame with the full assistant content, followed by `citations` and
    `done`. Cross-user access to the session (a race between the endpoint's
    ownership check and the runner's own check) surfaces as an `error` event.
    Any other failure is truncated + surfaced as `error` — no stack trace on
    the wire.
    """
    try:
        row = await runner(session_id, user_id, content)
    except PermissionError:
        yield _sse_event("error", {"message": "session not found"})
        return
    except Exception as exc:  # noqa: BLE001 — surface to client, don't crash
        log.exception(
            "chat SSE turn failed session=%s user=%s", session_id, user_id
        )
        yield _sse_event(
            "error", {"message": str(exc)[:200] or "chat turn failed"}
        )
        return

    yield _sse_event("token", {"delta": row.content or ""})
    yield _sse_event("citations", list(row.citations or []))
    yield _sse_event("done", {"message_id": str(row.id)})


@router.post(
    "/sessions/{session_id}/messages",
    name="post_chat_message",
)
async def post_chat_message(
    session_id: UUID,
    body: ChatMessageIn,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
    runner: TurnRunnerFn = Depends(get_chat_turn_runner),
) -> StreamingResponse:
    # Cross-user check up front — cheap 404 so we don't stream an error frame
    # for the obvious case. The runner also validates ownership; the
    # PermissionError path in the SSE generator is defence-in-depth for a race.
    await _get_owned_session(session_id, user.user_id, db)

    return StreamingResponse(
        _chat_sse_generator(session_id, user.user_id, body.content, runner),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
