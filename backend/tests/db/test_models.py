"""DATA-01 acceptance tests for the Phase 1 schema."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import models so Base.metadata is populated before create_all.
from app.db.base import Base  # noqa: F401
from app.db.models import (  # noqa: F401
    LlmCall,
    Portfolio,
    Position,
    Theme,
    UserPreferences,
)


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """A fresh sqlite scratch database per test, with FK enforcement on."""
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url, future=True)

    # sqlite doesn't enforce FKs by default; flip it on for every connection.
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
        # Windows can hold the sqlite file open briefly after engine.dispose();
        # temp files get GC'd eventually.
        pass


async def test_phase1_schema(session: AsyncSession):
    """Insert rows, hit every CHECK constraint, verify cascade delete."""
    user_id = uuid.uuid4()

    # --- happy path inserts across all four tables -------------------------
    session.add(
        UserPreferences(
            user_id=user_id,
            briefing_hour=9,
            briefing_timezone="America/New_York",
            display_currency="USD",
            model_tier="fast",
        )
    )
    portfolio = Portfolio(user_id=user_id, name="Main", is_active=True)
    session.add(portfolio)
    await session.flush()

    session.add(
        Position(
            portfolio_id=portfolio.id,
            ticker="NVDA",
            asset_type="equity",
            quantity=Decimal("10.25"),
            cost_basis=Decimal("450.0"),
            currency="USD",
            exchange="NASDAQ",
        )
    )
    session.add(
        Theme(
            user_id=user_id,
            description="AI capex cycle",
            weight=Decimal("0.80"),
        )
    )
    await session.commit()

    # Read back to confirm defaults applied.
    prefs = (
        await session.execute(select(UserPreferences).where(UserPreferences.user_id == user_id))
    ).scalar_one()
    assert prefs.briefing_hour == 9
    assert prefs.model_tier == "fast"

    # --- CHECK constraints ---------------------------------------------------

    # briefing_hour out of range
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                UserPreferences(
                    user_id=uuid.uuid4(),
                    briefing_hour=99,  # invalid
                    model_tier="thorough",
                )
            )
            await session.flush()

    # model_tier not in ('fast','thorough')
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                UserPreferences(
                    user_id=uuid.uuid4(),
                    briefing_hour=8,
                    model_tier="lightning",  # invalid
                )
            )
            await session.flush()

    # asset_type not in the allowlist
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                Position(
                    portfolio_id=portfolio.id,
                    ticker="TSLA",
                    asset_type="futures",  # invalid
                    exchange="NASDAQ",
                )
            )
            await session.flush()

    # weight out of [0, 1]
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                Theme(
                    user_id=user_id,
                    description="oversized weight",
                    weight=Decimal("1.50"),  # invalid
                )
            )
            await session.flush()

    # --- UNIQUE constraints --------------------------------------------------

    # (user_id, name) unique on portfolios
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(Portfolio(user_id=user_id, name="Main"))
            await session.flush()

    # (portfolio_id, ticker, exchange) unique on positions
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                Position(
                    portfolio_id=portfolio.id,
                    ticker="NVDA",
                    asset_type="equity",
                    exchange="NASDAQ",
                )
            )
            await session.flush()

    # --- Partial unique index: only one active portfolio per user -----------

    session.add(Portfolio(user_id=user_id, name="Retirement", is_active=False))
    await session.commit()

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(Portfolio(user_id=user_id, name="Experimental", is_active=True))
            await session.flush()

    # --- Cascade delete: dropping a portfolio drops its positions ----------

    positions_before = (
        await session.execute(
            select(Position).where(Position.portfolio_id == portfolio.id)
        )
    ).scalars().all()
    assert len(positions_before) == 1

    await session.delete(portfolio)
    await session.commit()

    positions_after = (
        await session.execute(
            select(Position).where(Position.portfolio_id == portfolio.id)
        )
    ).scalars().all()
    assert positions_after == []
