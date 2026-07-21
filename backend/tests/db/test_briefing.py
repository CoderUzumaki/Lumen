"""BRIEF-01 acceptance: briefings schema + Pydantic wire types + migration head."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.db.models import (  # noqa: F401 register with Base.metadata
    Briefing,
    Portfolio,
)
from app.schemas.briefing import BriefingContent, BriefingItem


# --- Fixtures ---------------------------------------------------------------


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Fresh sqlite via create_all() — fast; doesn't exercise migration DDL."""
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _):  # noqa: ARG001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s

    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass


async def _mk_portfolio(session: AsyncSession, user_id: uuid.UUID) -> Portfolio:
    p = Portfolio(user_id=user_id, name=f"pf-{uuid.uuid4().hex[:6]}", is_active=True)
    session.add(p)
    await session.flush()
    return p


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


# --- ORM roundtrip ----------------------------------------------------------


async def test_insert_and_read_full_row(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    impact_id = uuid.uuid4()
    content = _sample_content()

    row = Briefing(
        user_id=user_id,
        portfolio_id=pf.id,
        briefing_date=date(2026, 7, 20),
        structured_content=content,
        cited_impact_ids=[str(impact_id)],
        generation_duration_ms=1234,
        langsmith_run_id="run_briefing_1",
    )
    session.add(row)
    await session.commit()

    got = (
        await session.execute(select(Briefing).where(Briefing.id == row.id))
    ).scalar_one()
    assert got.briefing_date == date(2026, 7, 20)
    assert got.structured_content == content
    assert got.cited_impact_ids == [str(impact_id)]
    assert got.generation_duration_ms == 1234
    assert got.langsmith_run_id == "run_briefing_1"
    assert got.generated_at is not None


async def test_unique_constraint_on_user_portfolio_date(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    d = date(2026, 7, 20)

    session.add(
        Briefing(
            user_id=user_id,
            portfolio_id=pf.id,
            briefing_date=d,
            structured_content=_sample_content(),
            cited_impact_ids=[],
        )
    )
    await session.commit()

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                Briefing(
                    user_id=user_id,
                    portfolio_id=pf.id,  # same triple
                    briefing_date=d,
                    structured_content=_sample_content(),
                    cited_impact_ids=[],
                )
            )
            await session.flush()


async def test_portfolio_delete_cascades(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    session.add(
        Briefing(
            user_id=user_id,
            portfolio_id=pf.id,
            briefing_date=date(2026, 7, 20),
            structured_content=_sample_content(),
            cited_impact_ids=[],
        )
    )
    await session.commit()

    await session.delete(pf)
    await session.commit()
    session.expire_all()

    assert (await session.execute(select(Briefing))).scalars().all() == []


# --- Pydantic wire-shape validation ----------------------------------------


def _mk_item() -> BriefingItem:
    return BriefingItem(
        impact_id=uuid.uuid4(),
        cluster_title="Fed hikes 25bps",
        one_line_summary="Rate hike compresses growth multiples.",
        affected_positions=["QQQ"],
        mechanism_summary="Higher discount rates on long-dated cash flows.",
        confidence=0.6,
    )


def test_briefing_content_accepts_up_to_5_items():
    content = BriefingContent(
        top_movers=[_mk_item() for _ in range(5)],
        watchlist=[_mk_item() for _ in range(5)],
        what_would_change_my_thinking=["a", "b", "c", "d", "e"],
        generated_summary="ok",
    )
    assert len(content.top_movers) == 5
    assert len(content.watchlist) == 5
    assert len(content.what_would_change_my_thinking) == 5


def test_briefing_content_rejects_more_than_5_top_movers():
    with pytest.raises(ValidationError):
        BriefingContent(
            top_movers=[_mk_item() for _ in range(6)],
            watchlist=[],
            what_would_change_my_thinking=[],
            generated_summary="s",
        )


def test_briefing_content_rejects_more_than_5_watchlist():
    with pytest.raises(ValidationError):
        BriefingContent(
            top_movers=[],
            watchlist=[_mk_item() for _ in range(6)],
            what_would_change_my_thinking=[],
            generated_summary="s",
        )


def test_briefing_content_rejects_more_than_5_thinking():
    with pytest.raises(ValidationError):
        BriefingContent(
            top_movers=[],
            watchlist=[],
            what_would_change_my_thinking=["a", "b", "c", "d", "e", "f"],
            generated_summary="s",
        )


def test_briefing_item_confidence_bounded():
    ok = BriefingItem(
        impact_id=uuid.uuid4(),
        cluster_title="t",
        one_line_summary="s",
        affected_positions=["QQQ"],
        mechanism_summary="m",
        confidence=0.0,
    )
    assert ok.confidence == 0.0
    ok2 = BriefingItem(
        impact_id=uuid.uuid4(),
        cluster_title="t",
        one_line_summary="s",
        affected_positions=["QQQ"],
        mechanism_summary="m",
        confidence=1.0,
    )
    assert ok2.confidence == 1.0

    with pytest.raises(ValidationError):
        BriefingItem(
            impact_id=uuid.uuid4(),
            cluster_title="t",
            one_line_summary="s",
            affected_positions=["QQQ"],
            mechanism_summary="m",
            confidence=1.5,
        )
    with pytest.raises(ValidationError):
        BriefingItem(
            impact_id=uuid.uuid4(),
            cluster_title="t",
            one_line_summary="s",
            affected_positions=["QQQ"],
            mechanism_summary="m",
            confidence=-0.1,
        )


# --- Migration head + roundtrip --------------------------------------------


def _alembic_cfg() -> AlembicConfig:
    return AlembicConfig(str(Path(__file__).resolve().parents[2] / "alembic.ini"))


def _reenable_loggers() -> None:
    """Undo alembic env.py's fileConfig side effect (disables all loggers)."""
    import logging

    for name in list(logging.root.manager.loggerDict):
        logging.getLogger(name).disabled = False


def test_migration_head_is_briefing(tmp_path, monkeypatch):
    """Applying the chain up to BRIEF-01 must land on d4a91b7f5e28.

    We target `d4a91b7f5e28` explicitly rather than `head` because CHAT-01's
    migration (`e5b02c8f6a39`) chains after ours — the chain's actual head
    is downstream. This test scopes strictly to BRIEF-01.

    env.py resolves the DB URL from `DATABASE_URL` — set it to a fresh sqlite
    file for the duration of the test. See tests/db/test_impact.py for a
    detailed rationale on the logger-reenable step.
    """
    db_path = tmp_path / "brief01.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)

    command.upgrade(_alembic_cfg(), "d4a91b7f5e28")
    _reenable_loggers()

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            head = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert head == "d4a91b7f5e28"
    finally:
        engine.dispose()


def test_migration_roundtrip_upgrade_downgrade_upgrade(tmp_path, monkeypatch):
    """upgrade -> downgrade -1 -> upgrade cleanly, leaving head at BRIEF-01.

    Targets the BRIEF-01 revision explicitly so the assertion is invariant
    to any migrations CHAT-01 (or later modules) chain downstream.
    """
    db_path = tmp_path / "brief01_roundtrip.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)

    cfg = _alembic_cfg()
    command.upgrade(cfg, "d4a91b7f5e28")
    _reenable_loggers()

    command.downgrade(cfg, "-1")
    _reenable_loggers()

    command.upgrade(cfg, "d4a91b7f5e28")
    _reenable_loggers()

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            head = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            # Table must exist after the second upgrade.
            row = conn.execute(
                text("SELECT COUNT(*) FROM briefings")
            ).scalar_one()
        assert head == "d4a91b7f5e28"
        assert row == 0
    finally:
        engine.dispose()


# Reference `datetime` / `timezone` imports so lint doesn't drop them if
# we later add wall-clock assertions on `generated_at`.
_ = (datetime, timezone)
