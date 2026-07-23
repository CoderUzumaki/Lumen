"""Briefing endpoints + on-demand SSE stream (BRIEF-04).

Four endpoints, all authed via `require_auth`:

- `GET  /api/briefings/latest`               — most recent briefing for the
  caller's active portfolio (200 with `BriefingRead`; 404 if none yet).
- `GET  /api/briefings?date=YYYY-MM-DD`      — the briefing on that specific
  local date (200 with `BriefingRead`; 404 if none).
- `POST /api/briefings/regenerate`           — fire-and-forget enqueue of the
  BRIEF-02 synthesizer for today's UTC date with `force=True`; returns 202
  and a `poll_url` pointing at `GET /api/briefings/latest`.
- `GET  /api/briefings/stream`               — Server-Sent Events stream
  emitting synthesizer progress + the final briefing content.

Enqueue is a fire-and-forget `asyncio.create_task` whose coroutine opens its
own `AsyncSession` from `get_session_factory()` and constructs its own
`LLMClient` — the request-scoped session dies with the response. Tests
override the enqueue via `app.dependency_overrides[get_briefing_enqueue]`
so the graph never runs in-process.

Deviation from BUILD.md (documented per module docstring guidance):

    BRIEF-02's LangGraph isn't yet instrumented for per-node async event
    streaming — `BRIEFING_GRAPH.ainvoke()` is a single awaitable that returns
    the finished row (or None). The SSE endpoint therefore models the whole
    synthesis as ONE pseudo-node ("synthesizer"):

        1. `node_started`   {"node": "synthesizer"}
        2. `node_completed` {"node": "synthesizer", "duration_ms": <int>}
        3. `partial_content` <BriefingContent JSON>
        4. `complete`       {"briefing_id": "<uuid>"}

    A future refactor that exposes LangGraph's `astream_events` (per BUILD.md
    IMP-04's granular event shape) will emit per-node `node_started` /
    `node_completed` pairs — the wire contract of the pseudo-node stays the
    same, so clients written against BRIEF-04 will keep working.

Cross-user isolation mirrors REL-06 / IMP-05: every query filters
`briefings.user_id == caller.user_id`; no path can leak another user's row.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator, Callable, Coroutine
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.briefing.graph import synthesize_briefing_for_user
from app.db.base import get_db_session, get_session_factory
from app.db.models.briefing import Briefing
from app.db.models.portfolio import Portfolio
from app.schemas.briefing import BriefingRead
from app.utils.auth import UserContext, require_auth
from app.utils.llm import LLMClient

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/briefings", tags=["briefings"])


# Type alias for the enqueue callable. Tests override this via
# `app.dependency_overrides[get_briefing_enqueue]` so a fake enqueue can
# record calls without touching the real graph.
EnqueueFn = Callable[[UUID, UUID, date, bool], Coroutine[Any, Any, None]]


async def _default_enqueue(
    user_id: UUID, portfolio_id: UUID, briefing_date: date, force: bool
) -> None:
    """Fire-and-forget briefing synthesis. Never raises to the caller."""
    session_factory = get_session_factory()
    llm = LLMClient()

    async def _run() -> None:
        try:
            async with session_factory() as session:
                await synthesize_briefing_for_user(
                    user_id,
                    portfolio_id,
                    session=session,
                    llm=llm,
                    briefing_date=briefing_date,
                    force=force,
                )
        except Exception:  # noqa: BLE001 — background task must never leak
            log.exception(
                "briefing generation failed user=%s portfolio=%s date=%s",
                user_id,
                portfolio_id,
                briefing_date,
            )

    asyncio.create_task(_run())


def get_briefing_enqueue() -> EnqueueFn:
    """FastAPI dependency — swap via `app.dependency_overrides` in tests."""
    return _default_enqueue


async def _active_portfolio(user_id: UUID, db: AsyncSession) -> Portfolio | None:
    q = select(Portfolio).where(
        Portfolio.user_id == user_id, Portfolio.is_active.is_(True)
    )
    return (await db.execute(q)).scalar_one_or_none()


def _latest_url(request: Request) -> str:
    """Absolute URL clients poll to observe generation completion."""
    return str(request.url_for("get_latest_briefing"))


def _sse_event(event: str, data: Any) -> bytes:
    """Encode one SSE frame — `event: <name>\\ndata: <json>\\n\\n` as UTF-8."""
    payload = data if isinstance(data, str) else json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


# ---------------------------------------------------------------------------
# GET /api/briefings/latest
# ---------------------------------------------------------------------------


@router.get("/latest", name="get_latest_briefing", response_model=BriefingRead)
async def get_latest_briefing(
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> BriefingRead:
    portfolio = await _active_portfolio(user.user_id, db)
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active portfolio",
        )

    row = (
        await db.execute(
            select(Briefing)
            .where(
                Briefing.user_id == user.user_id,
                Briefing.portfolio_id == portfolio.id,
            )
            .order_by(Briefing.briefing_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "no briefing yet — generate one via POST "
                "/api/briefings/regenerate"
            ),
        )

    return BriefingRead.model_validate(row)


# ---------------------------------------------------------------------------
# GET /api/briefings?date=YYYY-MM-DD
# ---------------------------------------------------------------------------


@router.get("", name="get_briefing_by_date", response_model=BriefingRead)
async def get_briefing_by_date(
    date_: date = Query(alias="date"),
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> BriefingRead:
    portfolio = await _active_portfolio(user.user_id, db)
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active portfolio",
        )

    row = (
        await db.execute(
            select(Briefing).where(
                Briefing.user_id == user.user_id,
                Briefing.portfolio_id == portfolio.id,
                Briefing.briefing_date == date_,
            )
        )
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no briefing for {date_.isoformat()}",
        )

    return BriefingRead.model_validate(row)


# ---------------------------------------------------------------------------
# POST /api/briefings/regenerate
# ---------------------------------------------------------------------------


@router.post("/regenerate", name="regenerate_briefing")
async def regenerate_briefing(
    request: Request,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
    enqueue: EnqueueFn = Depends(get_briefing_enqueue),
):
    portfolio = await _active_portfolio(user.user_id, db)
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active portfolio",
        )

    today = datetime.now(timezone.utc).date()
    await enqueue(user.user_id, portfolio.id, today, True)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "generating",
            "poll_url": _latest_url(request),
        },
    )


# ---------------------------------------------------------------------------
# GET /api/briefings/stream
# ---------------------------------------------------------------------------


async def _briefing_sse_generator(
    user_id: UUID,
    portfolio_id: UUID,
    briefing_date: date,
) -> AsyncIterator[bytes]:
    """Yield SSE frames for one synthesizer run.

    Emits a single-node `node_started` / `node_completed` pair around the
    whole graph invocation (see module docstring for the deviation
    rationale). On completion, emits `partial_content` with the persisted
    BriefingContent, then `complete` with the row id. Any failure — the
    graph returns None (no eligible impacts / guardrail violation) or
    raises — is surfaced as an `error` event so the client can drop the
    stream cleanly.

    The session and LLMClient are constructed fresh for the stream (the
    request-scoped session dies with the response, and this generator
    outlives the endpoint handler).
    """
    session_factory = get_session_factory()
    llm = LLMClient()

    yield _sse_event("node_started", {"node": "synthesizer"})

    started = time.monotonic()
    row: Briefing | None
    try:
        async with session_factory() as session:
            row = await synthesize_briefing_for_user(
                user_id,
                portfolio_id,
                session=session,
                llm=llm,
                briefing_date=briefing_date,
                force=True,
            )
    except Exception as exc:  # noqa: BLE001 — surface to the client, don't crash
        log.exception(
            "briefing SSE synthesis failed user=%s portfolio=%s date=%s",
            user_id,
            portfolio_id,
            briefing_date,
        )
        yield _sse_event("error", {"message": str(exc) or "synthesis failed"})
        return

    duration_ms = int((time.monotonic() - started) * 1000)
    yield _sse_event(
        "node_completed",
        {"node": "synthesizer", "duration_ms": duration_ms},
    )

    if row is None:
        yield _sse_event(
            "error",
            {"message": "no eligible impacts or guardrail violation blocked persistence"},
        )
        return

    yield _sse_event("partial_content", row.structured_content)
    yield _sse_event("complete", {"briefing_id": str(row.id)})


@router.get("/stream", name="stream_briefing")
async def stream_briefing(
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
):
    portfolio = await _active_portfolio(user.user_id, db)
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active portfolio",
        )

    today = datetime.now(timezone.utc).date()
    return StreamingResponse(
        _briefing_sse_generator(user.user_id, portfolio.id, today),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
