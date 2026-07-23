"""BRIEF-04 acceptance: /api/briefings + /latest + /regenerate + /stream."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base, get_db_session
from app.db.models import (  # noqa: F401 register with Base.metadata
    Briefing,
    Portfolio,
)
from app.main import app
from app.routes.briefings import EnqueueFn, get_briefing_enqueue
from app.utils.auth import UserContext, require_auth

ALICE = uuid.uuid4()
BOB = uuid.uuid4()


def _fake_user_factory(user_id: uuid.UUID):
    async def _fake() -> UserContext:
        return UserContext(
            user_id=user_id, email=f"{user_id}@test", role="authenticated"
        )

    return _fake


class _EnqueueRecorder:
    """Test double for the briefing-generation enqueue callable.

    The default enqueue fires an `asyncio.create_task` that constructs a real
    `LLMClient`. Tests replace the dependency with an instance of this class
    so they can:
    - assert the enqueue was (or wasn't) called
    - assert the parameters passed
    - optionally have the enqueue synchronously persist a row so the
      "poll returns 200" flow can be exercised without touching the graph
    """

    def __init__(
        self,
        *,
        on_call: EnqueueFn | None = None,
    ) -> None:
        self.calls: list[tuple[uuid.UUID, uuid.UUID, date, bool]] = []
        self._on_call = on_call

    async def __call__(
        self,
        user_id: uuid.UUID,
        portfolio_id: uuid.UUID,
        briefing_date: date,
        force: bool,
    ) -> None:
        self.calls.append((user_id, portfolio_id, briefing_date, force))
        if self._on_call is not None:
            await self._on_call(user_id, portfolio_id, briefing_date, force)


@pytest_asyncio.fixture
async def env() -> AsyncIterator[
    tuple[AsyncClient, async_sessionmaker[AsyncSession], _EnqueueRecorder]
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

    enqueue = _EnqueueRecorder()

    app.dependency_overrides[get_db_session] = _session_override
    app.dependency_overrides[require_auth] = _fake_user_factory(ALICE)
    app.dependency_overrides[get_briefing_enqueue] = lambda: enqueue

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c, session_factory, enqueue

    app.dependency_overrides.clear()
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


async def _seed_portfolio(
    session: AsyncSession, user_id: uuid.UUID, *, active: bool = True
) -> Portfolio:
    pf = Portfolio(
        user_id=user_id, name=f"pf-{uuid.uuid4().hex[:6]}", is_active=active
    )
    session.add(pf)
    await session.commit()
    await session.refresh(pf)
    return pf


def _sample_content() -> dict:
    return {
        "top_movers": [
            {
                "impact_id": str(uuid.uuid4()),
                "cluster_title": "Fed hikes 25bps",
                "one_line_summary": "Rate hike compresses growth multiples.",
                "affected_positions": ["QQQ"],
                "mechanism_summary": "Higher discount rates on long-dated cash flows.",
                "confidence": 0.7,
            }
        ],
        "watchlist": [],
        "what_would_change_my_thinking": ["10y yield inverts within a week."],
        "generated_summary": "Rates up; growth pressured.",
    }


async def _seed_briefing(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    portfolio_id: uuid.UUID,
    briefing_date: date,
    content: dict | None = None,
) -> Briefing:
    row = Briefing(
        user_id=user_id,
        portfolio_id=portfolio_id,
        briefing_date=briefing_date,
        structured_content=content or _sample_content(),
        cited_impact_ids=[],
        generation_duration_ms=1000,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# GET /api/briefings/latest
# ---------------------------------------------------------------------------


async def test_latest_returns_most_recent_briefing(env):
    client, factory, _ = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        await _seed_briefing(
            s,
            user_id=ALICE,
            portfolio_id=pf.id,
            briefing_date=date(2026, 7, 20),
        )
        newer = await _seed_briefing(
            s,
            user_id=ALICE,
            portfolio_id=pf.id,
            briefing_date=date(2026, 7, 22),
        )

    r = await client.get("/api/briefings/latest")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(newer.id)
    assert body["briefing_date"] == "2026-07-22"


async def test_latest_404_when_none_exist(env):
    client, factory, _ = env
    async with factory() as s:
        await _seed_portfolio(s, ALICE)  # portfolio but no briefings

    r = await client.get("/api/briefings/latest")
    assert r.status_code == 404, r.text
    # Envelope handler wraps detail as `error.message`.
    assert "regenerate" in r.text.lower()


async def test_latest_404_when_no_active_portfolio(env):
    client, factory, _ = env
    # Alice has no portfolio at all — sanity-only session use.
    async with factory() as s:
        assert s is not None

    r = await client.get("/api/briefings/latest")
    assert r.status_code == 404
    assert "portfolio" in r.text.lower()


# ---------------------------------------------------------------------------
# GET /api/briefings?date=YYYY-MM-DD
# ---------------------------------------------------------------------------


async def test_get_by_date_returns_matching_briefing(env):
    client, factory, _ = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        await _seed_briefing(
            s, user_id=ALICE, portfolio_id=pf.id, briefing_date=date(2026, 7, 19)
        )
        target = await _seed_briefing(
            s, user_id=ALICE, portfolio_id=pf.id, briefing_date=date(2026, 7, 20)
        )
        await _seed_briefing(
            s, user_id=ALICE, portfolio_id=pf.id, briefing_date=date(2026, 7, 21)
        )

    r = await client.get("/api/briefings", params={"date": "2026-07-20"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(target.id)
    assert body["briefing_date"] == "2026-07-20"


async def test_get_by_date_404_when_missing(env):
    client, factory, _ = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        await _seed_briefing(
            s, user_id=ALICE, portfolio_id=pf.id, briefing_date=date(2026, 7, 19)
        )

    r = await client.get("/api/briefings", params={"date": "2026-07-25"})
    assert r.status_code == 404, r.text


async def test_get_by_date_missing_query_param_400(env):
    client, factory, _ = env
    async with factory() as s:
        await _seed_portfolio(s, ALICE)

    r = await client.get("/api/briefings")
    # Main.py's RequestValidationError handler remaps 422 → 400.
    assert r.status_code == 400, r.text
    assert "validation" in r.text.lower()


# ---------------------------------------------------------------------------
# POST /api/briefings/regenerate
# ---------------------------------------------------------------------------


async def test_regenerate_returns_202_and_enqueues_with_force(env):
    client, factory, enqueue = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)

    r = await client.post("/api/briefings/regenerate")
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "generating"
    assert body["poll_url"].endswith("/api/briefings/latest")

    assert len(enqueue.calls) == 1
    uid, pid, bd, force = enqueue.calls[0]
    assert uid == ALICE
    assert pid == pf.id
    assert bd == datetime.now(timezone.utc).date()
    assert force is True


async def test_regenerate_404_when_no_active_portfolio(env):
    client, _, enqueue = env
    r = await client.post("/api/briefings/regenerate")
    assert r.status_code == 404
    assert enqueue.calls == []


# ---------------------------------------------------------------------------
# GET /api/briefings/stream
# ---------------------------------------------------------------------------


async def test_stream_returns_sse_content_type(env, monkeypatch):
    client, factory, _ = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)

    # The SSE generator opens its own session via the module-level
    # `get_session_factory()` — which points at the real DATABASE_URL. Redirect
    # that lookup at the test's sqlite factory so the fake synth can persist.
    monkeypatch.setattr(
        "app.routes.briefings.get_session_factory", lambda: factory
    )

    # Replace the module-level synthesizer with a fake so the stream can run
    # without Chroma / a live LLM. The fake persists a real briefings row so
    # the generator emits `partial_content` + `complete` (not `error`).
    async def _fake_synth(
        user_id, portfolio_id, *, session, llm, briefing_date, force
    ):
        row = Briefing(
            user_id=user_id,
            portfolio_id=portfolio_id,
            briefing_date=briefing_date,
            structured_content=_sample_content(),
            cited_impact_ids=[],
            generation_duration_ms=42,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row

    monkeypatch.setattr(
        "app.routes.briefings.synthesize_briefing_for_user", _fake_synth
    )
    # Also stub out LLMClient so its __init__ doesn't touch config.
    monkeypatch.setattr(
        "app.routes.briefings.LLMClient", lambda *a, **k: object()
    )

    r = await client.get("/api/briefings/stream")
    assert r.status_code == 200, r.text
    ctype = r.headers.get("content-type", "")
    assert ctype.startswith("text/event-stream"), ctype
    body = r.text
    assert "event: node_started" in body
    assert "event: node_completed" in body
    assert "event: partial_content" in body
    assert "event: complete" in body
    assert pf.id  # sanity


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


async def test_cross_user_isolation(env):
    """Alice's /latest doesn't return a briefing row seeded for Bob."""
    client, factory, _ = env
    async with factory() as s:
        # Alice has an active portfolio but NO briefings.
        await _seed_portfolio(s, ALICE)
        # Bob has both a portfolio and a briefing.
        pf_bob = await _seed_portfolio(s, BOB)
        await _seed_briefing(
            s,
            user_id=BOB,
            portfolio_id=pf_bob.id,
            briefing_date=date(2026, 7, 22),
        )

    r = await client.get("/api/briefings/latest")
    assert r.status_code == 404, r.text
