"""CHAT-04 acceptance: /api/chat/sessions CRUD + /messages SSE stream."""
from __future__ import annotations

import asyncio
import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base, get_db_session
from app.db.models import (  # noqa: F401 register with Base.metadata
    ChatMessage,
    ChatSession,
    NewsCluster,
    Portfolio,
)
from app.main import app
from app.routes.chat import TurnRunnerFn, get_chat_turn_runner
from app.utils.auth import UserContext, require_auth

ALICE = uuid.uuid4()
BOB = uuid.uuid4()


def _fake_user_factory(user_id: uuid.UUID):
    async def _fake() -> UserContext:
        return UserContext(
            user_id=user_id, email=f"{user_id}@test", role="authenticated"
        )

    return _fake


class _TurnRunnerStub:
    """Test double for the chat-turn runner.

    The default runner would construct real `LLMClient` / `VectorStore` /
    `EmbeddingClient` instances and drive the CHAT-03 graph. This stub
    persists a canned assistant `ChatMessage` on the injected session_factory
    (so the endpoint's SSE generator can serialize it) and records the call
    args for assertions.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        content: str = "hello world",
        citations: list[dict] | None = None,
        raises: BaseException | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.content = content
        self.citations = citations if citations is not None else []
        self.raises = raises
        self.calls: list[tuple[uuid.UUID, uuid.UUID, str]] = []

    async def __call__(
        self, session_id: uuid.UUID, user_id: uuid.UUID, content: str
    ) -> ChatMessage:
        self.calls.append((session_id, user_id, content))
        if self.raises is not None:
            raise self.raises
        async with self.session_factory() as s:
            row = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=self.content,
                citations=list(self.citations),
                tokens_used=None,
                guardrail_violations=[],
            )
            s.add(row)
            await s.commit()
            await s.refresh(row)
            return row


@pytest_asyncio.fixture
async def env() -> AsyncIterator[
    tuple[
        AsyncClient,
        async_sessionmaker[AsyncSession],
        dict[str, TurnRunnerFn | None],
    ]
]:
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}", future=True
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _):  # noqa: ARG001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _session_override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            yield s

    # Mutable slot so tests can inject a bespoke runner after fixture setup.
    slot: dict[str, TurnRunnerFn | None] = {"runner": None}

    def _runner_override() -> TurnRunnerFn:
        runner = slot["runner"]
        if runner is None:
            # Fallback: no-op that would fail if actually invoked.
            async def _noop(*_a, **_kw):  # pragma: no cover - defensive
                raise AssertionError(
                    "test forgot to install a runner via slot['runner']"
                )

            return _noop
        return runner

    app.dependency_overrides[get_db_session] = _session_override
    app.dependency_overrides[require_auth] = _fake_user_factory(ALICE)
    app.dependency_overrides[get_chat_turn_runner] = _runner_override

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c, session_factory, slot

    app.dependency_overrides.clear()
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


async def _seed_portfolio(
    session: AsyncSession, user_id: uuid.UUID, *, active: bool = True
) -> Portfolio:
    pf = Portfolio(
        user_id=user_id,
        name=f"pf-{uuid.uuid4().hex[:6]}",
        is_active=active,
    )
    session.add(pf)
    await session.commit()
    await session.refresh(pf)
    return pf


async def _seed_chat_session(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    portfolio_id: uuid.UUID,
    title: str = "test chat",
    updated_at: datetime | None = None,
) -> ChatSession:
    row = ChatSession(
        user_id=user_id, portfolio_id=portfolio_id, title=title
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    if updated_at is not None:
        await session.execute(
            update(ChatSession)
            .where(ChatSession.id == row.id)
            .values(updated_at=updated_at)
        )
        await session.commit()
        await session.refresh(row)
    return row


async def _seed_cluster(session: AsyncSession) -> NewsCluster:
    now = datetime.now(timezone.utc)
    cluster = NewsCluster(
        canonical_title="Fed hikes 25bps",
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=[],
        entity_topics=[],
        member_sources=["newsapi"],
    )
    session.add(cluster)
    await session.commit()
    await session.refresh(cluster)
    return cluster


# ---------------------------------------------------------------------------
# POST /api/chat/sessions
# ---------------------------------------------------------------------------


async def test_create_session_returns_201(env):
    client, factory, _ = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)

    r = await client.post("/api/chat/sessions", json={})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user_id"] == str(ALICE)
    assert body["portfolio_id"] == str(pf.id)
    assert body["title"] is None
    assert body["seed_cluster_id"] is None
    assert body["messages"] == []


async def test_create_session_404_when_no_active_portfolio(env):
    client, _, _ = env
    r = await client.post("/api/chat/sessions", json={"title": "orphan"})
    assert r.status_code == 404, r.text
    assert "portfolio" in r.text.lower()


async def test_create_session_400_when_seed_cluster_unknown(env):
    client, factory, _ = env
    async with factory() as s:
        await _seed_portfolio(s, ALICE)

    r = await client.post(
        "/api/chat/sessions",
        json={"seed_cluster_id": str(uuid.uuid4())},
    )
    assert r.status_code == 400, r.text
    assert "seed_cluster_id" in r.text or "cluster" in r.text.lower()


# ---------------------------------------------------------------------------
# GET /api/chat/sessions
# ---------------------------------------------------------------------------


async def test_list_sessions_orders_by_updated_at_desc(env):
    client, factory, _ = env
    base = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        oldest = await _seed_chat_session(
            s, user_id=ALICE, portfolio_id=pf.id,
            title="oldest", updated_at=base,
        )
        newest = await _seed_chat_session(
            s, user_id=ALICE, portfolio_id=pf.id,
            title="newest", updated_at=base + timedelta(hours=2),
        )
        middle = await _seed_chat_session(
            s, user_id=ALICE, portfolio_id=pf.id,
            title="middle", updated_at=base + timedelta(hours=1),
        )

    r = await client.get("/api/chat/sessions")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 3
    assert [row["id"] for row in body] == [
        str(newest.id), str(middle.id), str(oldest.id)
    ]
    assert all(row["messages"] == [] for row in body)


async def test_list_sessions_excludes_other_users(env):
    client, factory, _ = env
    async with factory() as s:
        pf_alice = await _seed_portfolio(s, ALICE)
        pf_bob = await _seed_portfolio(s, BOB)
        await _seed_chat_session(s, user_id=ALICE, portfolio_id=pf_alice.id)
        bob_session = await _seed_chat_session(
            s, user_id=BOB, portfolio_id=pf_bob.id
        )

    r = await client.get("/api/chat/sessions")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["user_id"] == str(ALICE)
    assert body[0]["id"] != str(bob_session.id)


# ---------------------------------------------------------------------------
# GET /api/chat/sessions/{id}
# ---------------------------------------------------------------------------


async def test_get_session_returns_messages_in_order(env):
    client, factory, _ = env
    base = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        chat = await _seed_chat_session(s, user_id=ALICE, portfolio_id=pf.id)

        # Insert three messages with explicit staggered created_at values.
        m1 = ChatMessage(
            session_id=chat.id, role="user", content="first", citations=[]
        )
        m2 = ChatMessage(
            session_id=chat.id, role="assistant", content="second",
            citations=[],
        )
        m3 = ChatMessage(
            session_id=chat.id, role="user", content="third", citations=[]
        )
        s.add_all([m1, m2, m3])
        await s.commit()
        for m, offset in ((m1, 0), (m2, 1), (m3, 2)):
            await s.execute(
                update(ChatMessage)
                .where(ChatMessage.id == m.id)
                .values(created_at=base + timedelta(seconds=offset))
            )
        await s.commit()

    r = await client.get(f"/api/chat/sessions/{chat.id}")
    assert r.status_code == 200, r.text
    body = r.json()
    contents = [m["content"] for m in body["messages"]]
    assert contents == ["first", "second", "third"]


async def test_get_session_404_for_other_users_session(env):
    client, factory, _ = env
    async with factory() as s:
        pf_bob = await _seed_portfolio(s, BOB)
        bob_session = await _seed_chat_session(
            s, user_id=BOB, portfolio_id=pf_bob.id
        )

    r = await client.get(f"/api/chat/sessions/{bob_session.id}")
    assert r.status_code == 404, r.text
    assert "forbidden" not in r.text.lower()


async def test_get_session_404_for_unknown_id(env):
    client, _, _ = env
    r = await client.get(f"/api/chat/sessions/{uuid.uuid4()}")
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# DELETE /api/chat/sessions/{id}
# ---------------------------------------------------------------------------


async def test_delete_session_returns_204_and_cascades_messages(env):
    client, factory, _ = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        chat = await _seed_chat_session(s, user_id=ALICE, portfolio_id=pf.id)
        s.add(
            ChatMessage(
                session_id=chat.id, role="user", content="hi", citations=[]
            )
        )
        await s.commit()

    r = await client.delete(f"/api/chat/sessions/{chat.id}")
    assert r.status_code == 204, r.text
    assert r.text == ""

    async with factory() as s:
        remaining_msgs = (
            await s.execute(
                select(ChatMessage).where(ChatMessage.session_id == chat.id)
            )
        ).scalars().all()
        remaining_sessions = (
            await s.execute(
                select(ChatSession).where(ChatSession.id == chat.id)
            )
        ).scalars().all()
    assert remaining_msgs == []
    assert remaining_sessions == []


async def test_delete_session_404_for_other_users_session(env):
    client, factory, _ = env
    async with factory() as s:
        pf_bob = await _seed_portfolio(s, BOB)
        bob_session = await _seed_chat_session(
            s, user_id=BOB, portfolio_id=pf_bob.id
        )

    r = await client.delete(f"/api/chat/sessions/{bob_session.id}")
    assert r.status_code == 404, r.text

    async with factory() as s:
        still_there = (
            await s.execute(
                select(ChatSession).where(ChatSession.id == bob_session.id)
            )
        ).scalar_one_or_none()
    assert still_there is not None


# ---------------------------------------------------------------------------
# POST /api/chat/sessions/{id}/messages  (SSE)
# ---------------------------------------------------------------------------


async def test_post_message_returns_sse_stream_with_token_citations_done(env):
    client, factory, slot = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        chat = await _seed_chat_session(s, user_id=ALICE, portfolio_id=pf.id)

    citation = {
        "source": "reuters",
        "url": "https://reuters.example/fed",
        "title": "Fed hikes 25bps",
        "quote": "raised rates by a quarter point",
    }
    slot["runner"] = _TurnRunnerStub(
        session_factory=factory,
        content="hello world",
        citations=[citation],
    )

    r = await client.post(
        f"/api/chat/sessions/{chat.id}/messages",
        json={"content": "What did the Fed do?"},
    )
    assert r.status_code == 200, r.text
    ctype = r.headers.get("content-type", "")
    assert ctype.startswith("text/event-stream"), ctype

    body = r.text
    token_idx = body.find("event: token")
    citations_idx = body.find("event: citations")
    done_idx = body.find("event: done")

    assert token_idx != -1, body
    assert citations_idx != -1, body
    assert done_idx != -1, body
    assert token_idx < citations_idx < done_idx
    assert "hello world" in body
    assert "reuters.example" in body

    # Runner was invoked exactly once with the right args.
    stub = slot["runner"]
    assert isinstance(stub, _TurnRunnerStub)
    assert len(stub.calls) == 1
    sid, uid, content = stub.calls[0]
    assert sid == chat.id
    assert uid == ALICE
    assert content == "What did the Fed do?"


async def test_post_message_permission_error_becomes_error_event(env):
    client, factory, slot = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        chat = await _seed_chat_session(s, user_id=ALICE, portfolio_id=pf.id)

    slot["runner"] = _TurnRunnerStub(
        session_factory=factory,
        raises=PermissionError("cross-user"),
    )

    r = await client.post(
        f"/api/chat/sessions/{chat.id}/messages",
        json={"content": "hello"},
    )
    assert r.status_code == 200, r.text
    body = r.text
    assert "event: error" in body
    assert "session not found" in body
    # Success frames must NOT be present on the error path.
    assert "event: done" not in body


async def test_post_message_body_validation_content_too_long(env):
    client, factory, slot = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        chat = await _seed_chat_session(s, user_id=ALICE, portfolio_id=pf.id)

    # Ensure the runner is not invoked when validation fails.
    stub = _TurnRunnerStub(session_factory=factory)
    slot["runner"] = stub

    r = await client.post(
        f"/api/chat/sessions/{chat.id}/messages",
        json={"content": "x" * 5000},
    )
    # Main.py's RequestValidationError handler remaps 422 → 400.
    assert r.status_code == 400, r.text
    assert "validation" in r.text.lower()
    assert stub.calls == []


# Silence unused-import warnings via a trivial no-op reference at import time
# — some flake configs flag `asyncio` if the fixture-only path never uses it.
_ = asyncio
