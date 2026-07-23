"""BRIEF-03 acceptance: scheduled briefing generation, timezone-aware."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.db.models import (  # noqa: F401 register with Base.metadata
    Briefing,
    Portfolio,
    UserPreferences,
)
from app.pipelines.briefing_scheduler import (
    BriefingSchedulerSummary,
    run_briefing_scheduler,
)
from app.utils.llm import LLMClient


@pytest_asyncio.fixture
async def factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
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
    yield session_factory
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass


class _FakeLLM(LLMClient):
    """Never actually called — the fake synthesizer bypasses the LLM path."""

    def __init__(self) -> None:
        super().__init__(http_client=AsyncMock())


async def _mk_pref(
    session: AsyncSession, user_id: uuid.UUID, *, hour: int, tz: str
) -> UserPreferences:
    row = UserPreferences(
        user_id=user_id, briefing_hour=hour, briefing_timezone=tz
    )
    session.add(row)
    await session.commit()
    return row


async def _mk_portfolio(
    session: AsyncSession, user_id: uuid.UUID, *, active: bool = True
) -> Portfolio:
    p = Portfolio(
        user_id=user_id,
        name=f"pf-{uuid.uuid4().hex[:6]}",
        is_active=active,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


def _make_recording_synthesizer():
    """Return `(synth_fn, calls_list)` — synth writes a Briefing row + records the call."""
    calls: list[tuple[uuid.UUID, uuid.UUID, date]] = []

    async def _synth(user_id, portfolio_id, session, llm, briefing_date):
        calls.append((user_id, portfolio_id, briefing_date))
        row = Briefing(
            user_id=user_id,
            portfolio_id=portfolio_id,
            briefing_date=briefing_date,
            structured_content={
                "top_movers": [], "watchlist": [],
                "what_would_change_my_thinking": [],
                "generated_summary": "test",
            },
            cited_impact_ids=[],
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row

    return _synth, calls


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_matching_local_hour_generates_briefing(factory):
    """08:00 IST → user with briefing_hour=8, tz=Asia/Kolkata gets briefed."""
    async with factory() as s:
        user_id = uuid.uuid4()
        await _mk_pref(s, user_id, hour=8, tz="Asia/Kolkata")
        pf = await _mk_portfolio(s, user_id)

    # 08:15 IST == 02:45 UTC on the same UTC date.
    now_utc = datetime(2026, 7, 21, 2, 45, tzinfo=timezone.utc)
    synth, calls = _make_recording_synthesizer()

    summary = await run_briefing_scheduler(
        session_factory=factory,
        llm=_FakeLLM(),
        now=now_utc,
        synthesizer=synth,
    )

    assert isinstance(summary, BriefingSchedulerSummary)
    assert summary.candidates_considered == 1
    assert summary.generated == 1
    assert len(calls) == 1
    assert calls[0][0] == user_id
    assert calls[0][1] == pf.id
    # IST local date at 08:15 IST on 2026-07-21 UTC is 2026-07-21.
    assert calls[0][2] == date(2026, 7, 21)


async def test_non_matching_hour_skipped(factory):
    async with factory() as s:
        user_id = uuid.uuid4()
        await _mk_pref(s, user_id, hour=8, tz="UTC")
        await _mk_portfolio(s, user_id)

    # 07:30 UTC — hour 7, not 8.
    now_utc = datetime(2026, 7, 21, 7, 30, tzinfo=timezone.utc)
    synth, calls = _make_recording_synthesizer()
    summary = await run_briefing_scheduler(
        session_factory=factory, llm=_FakeLLM(), now=now_utc, synthesizer=synth
    )
    assert summary.candidates_considered == 0
    assert summary.generated == 0
    assert calls == []


async def test_no_active_portfolio_skipped(factory):
    async with factory() as s:
        user_id = uuid.uuid4()
        await _mk_pref(s, user_id, hour=8, tz="UTC")
        await _mk_portfolio(s, user_id, active=False)  # inactive

    now_utc = datetime(2026, 7, 21, 8, 5, tzinfo=timezone.utc)
    synth, calls = _make_recording_synthesizer()
    summary = await run_briefing_scheduler(
        session_factory=factory, llm=_FakeLLM(), now=now_utc, synthesizer=synth
    )
    assert summary.candidates_considered == 1
    assert summary.skipped_no_active_portfolio == 1
    assert summary.generated == 0
    assert calls == []


async def test_existing_briefing_skipped(factory):
    """Idempotency: a briefing already there for today's LOCAL date → skip."""
    async with factory() as s:
        user_id = uuid.uuid4()
        await _mk_pref(s, user_id, hour=8, tz="UTC")
        pf = await _mk_portfolio(s, user_id)
        s.add(
            Briefing(
                user_id=user_id,
                portfolio_id=pf.id,
                briefing_date=date(2026, 7, 21),
                structured_content={
                    "top_movers": [], "watchlist": [],
                    "what_would_change_my_thinking": [],
                    "generated_summary": "already there",
                },
                cited_impact_ids=[],
            )
        )
        await s.commit()

    now_utc = datetime(2026, 7, 21, 8, 5, tzinfo=timezone.utc)
    synth, calls = _make_recording_synthesizer()
    summary = await run_briefing_scheduler(
        session_factory=factory, llm=_FakeLLM(), now=now_utc, synthesizer=synth
    )
    assert summary.candidates_considered == 1
    assert summary.skipped_already_exists == 1
    assert summary.generated == 0
    assert calls == []


async def test_unknown_timezone_skipped_gracefully(factory):
    async with factory() as s:
        user_id = uuid.uuid4()
        await _mk_pref(s, user_id, hour=8, tz="Not/A/Zone")
        await _mk_portfolio(s, user_id)

    now_utc = datetime(2026, 7, 21, 8, 5, tzinfo=timezone.utc)
    synth, calls = _make_recording_synthesizer()
    summary = await run_briefing_scheduler(
        session_factory=factory, llm=_FakeLLM(), now=now_utc, synthesizer=synth
    )
    assert summary.skipped_unknown_timezone == 1
    assert summary.generated == 0
    assert calls == []


async def test_two_users_two_timezones_both_hit_at_local_8am(factory):
    """One UTC user at 8am, one IST user whose 8am is the same UTC moment."""
    async with factory() as s:
        alice = uuid.uuid4()  # UTC, briefing_hour=8
        bob = uuid.uuid4()    # Asia/Kolkata, briefing_hour=13:30-local == 08:00 UTC
        # bob at hour=8 IST → 02:30 UTC. We want a single UTC moment where BOTH match.
        # UTC 08:00, alice=8 → match. bob's local hour at UTC 08:00 with IST (+5:30) is 13.
        # Set bob's briefing_hour=13 so both match at the same UTC moment.
        await _mk_pref(s, alice, hour=8, tz="UTC")
        await _mk_pref(s, bob, hour=13, tz="Asia/Kolkata")
        await _mk_portfolio(s, alice)
        await _mk_portfolio(s, bob)

    now_utc = datetime(2026, 7, 21, 8, 5, tzinfo=timezone.utc)
    synth, calls = _make_recording_synthesizer()
    summary = await run_briefing_scheduler(
        session_factory=factory, llm=_FakeLLM(), now=now_utc, synthesizer=synth
    )
    assert summary.candidates_considered == 2
    assert summary.generated == 2
    user_ids = {c[0] for c in calls}
    assert user_ids == {alice, bob}
    # Alice's local date (UTC) at 08:05 UTC is 2026-07-21.
    # Bob's local date (IST) at 13:35 IST on 2026-07-21 is also 2026-07-21.
    for _, _, bd in calls:
        assert bd == date(2026, 7, 21)


async def test_synthesizer_returning_none_counted_no_generation(factory):
    """A guardrail-rejected synthesis returns None; scheduler counts errors=0, generated=0."""
    async with factory() as s:
        user_id = uuid.uuid4()
        await _mk_pref(s, user_id, hour=8, tz="UTC")
        await _mk_portfolio(s, user_id)

    async def _null_synth(user_id, portfolio_id, session, llm, briefing_date):
        return None  # simulates guardrail rejection or empty candidates

    now_utc = datetime(2026, 7, 21, 8, 5, tzinfo=timezone.utc)
    summary = await run_briefing_scheduler(
        session_factory=factory,
        llm=_FakeLLM(),
        now=now_utc,
        synthesizer=_null_synth,
    )
    assert summary.candidates_considered == 1
    assert summary.generated == 0
    assert summary.errors == 0


async def test_synthesizer_raising_counted_as_error(factory):
    async with factory() as s:
        user_id = uuid.uuid4()
        await _mk_pref(s, user_id, hour=8, tz="UTC")
        await _mk_portfolio(s, user_id)

    async def _boom_synth(*_args, **_kwargs):
        raise RuntimeError("boom")

    now_utc = datetime(2026, 7, 21, 8, 5, tzinfo=timezone.utc)
    summary = await run_briefing_scheduler(
        session_factory=factory,
        llm=_FakeLLM(),
        now=now_utc,
        synthesizer=_boom_synth,
    )
    assert summary.candidates_considered == 1
    assert summary.generated == 0
    assert summary.errors == 1


async def test_briefing_date_uses_user_local_date_not_utc(factory):
    """UTC crosses midnight but user's local time is still previous day."""
    async with factory() as s:
        user_id = uuid.uuid4()
        # New York briefing hour = 20 (8pm). At 20:15 EDT the UTC date has ALREADY
        # rolled to the next day (UTC-4 offset in summer).
        await _mk_pref(s, user_id, hour=20, tz="America/New_York")
        await _mk_portfolio(s, user_id)

    # 20:15 EDT on 2026-07-21 == 00:15 UTC on 2026-07-22.
    ny = ZoneInfo("America/New_York")
    now_local = datetime(2026, 7, 21, 20, 15, tzinfo=ny)
    now_utc = now_local.astimezone(timezone.utc)
    assert now_utc.date() == date(2026, 7, 22)  # sanity

    synth, calls = _make_recording_synthesizer()
    summary = await run_briefing_scheduler(
        session_factory=factory, llm=_FakeLLM(), now=now_utc, synthesizer=synth
    )
    assert summary.generated == 1
    assert calls[0][2] == date(2026, 7, 21)  # user's LOCAL date, not UTC


async def test_no_prefs_returns_zero_summary(factory):
    now_utc = datetime(2026, 7, 21, 8, 5, tzinfo=timezone.utc)
    summary = await run_briefing_scheduler(
        session_factory=factory, llm=_FakeLLM(), now=now_utc
    )
    assert summary.candidates_considered == 0
    assert summary.generated == 0
