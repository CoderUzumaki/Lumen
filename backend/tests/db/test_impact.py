"""IMP-01 acceptance: impact_assessments schema + Pydantic wire types."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone
from decimal import Decimal
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
    ImpactAssessment,
    NewsCluster,
    Portfolio,
)
from app.schemas.impact import (
    Citation,
    HistoricalAnalog,
    ImpactAssessment as ImpactAssessmentPayload,
)


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


async def _mk_cluster(session: AsyncSession) -> NewsCluster:
    now = datetime.now(timezone.utc)
    cluster = NewsCluster(
        canonical_title="Fed hikes",
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=["SPY"],
        entity_topics=[],
        member_sources=["newsapi"],
    )
    session.add(cluster)
    await session.flush()
    return cluster


async def _mk_portfolio(session: AsyncSession, user_id: uuid.UUID) -> Portfolio:
    p = Portfolio(user_id=user_id, name=f"pf-{uuid.uuid4().hex[:6]}", is_active=True)
    session.add(p)
    await session.flush()
    return p


def _sample_citation() -> dict:
    return {
        "source": "reuters",
        "url": "https://reuters.example/x",
        "title": "Fed decision",
        "quote": "The Fed raised rates by 25bps citing sticky inflation.",
    }


# --- ORM roundtrip ----------------------------------------------------------


async def test_insert_and_read_full_row(session: AsyncSession):
    cluster = await _mk_cluster(session)
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    pos_id = uuid.uuid4()

    row = ImpactAssessment(
        cluster_id=cluster.id,
        user_id=user_id,
        portfolio_id=pf.id,
        mechanism="Higher policy rates compress duration-sensitive equity valuations, "
        "raising discount rates on future cash flows and pressuring growth multiples.",
        magnitude_low=Decimal("-0.05"),
        magnitude_high=Decimal("-0.02"),
        timeframe_days=30,
        confidence=Decimal("0.65"),
        falsifiability="Thesis breaks if the 10y yield curve re-inverts within 5 sessions.",
        citations=[_sample_citation()],
        historical_analogs=[],
        affected_positions=[str(pos_id)],
        raw_llm_output="{...}",
        guardrail_violations=[],
        langsmith_run_id="run_abc123",
    )
    session.add(row)
    await session.commit()

    got = (
        await session.execute(select(ImpactAssessment).where(ImpactAssessment.id == row.id))
    ).scalar_one()
    assert got.mechanism.startswith("Higher policy rates")
    assert got.magnitude_low == Decimal("-0.05")
    assert got.confidence == Decimal("0.65")
    assert got.timeframe_days == 30
    assert got.citations == [_sample_citation()]
    assert got.affected_positions == [str(pos_id)]
    assert got.langsmith_run_id == "run_abc123"
    assert got.created_at is not None


async def test_unique_constraint_on_cluster_user_portfolio(session: AsyncSession):
    cluster = await _mk_cluster(session)
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)

    session.add(
        ImpactAssessment(
            cluster_id=cluster.id,
            user_id=user_id,
            portfolio_id=pf.id,
            mechanism="m" * 60,
            confidence=Decimal("0.5"),
            falsifiability="f" * 30,
            citations=[_sample_citation()],
            affected_positions=[str(uuid.uuid4())],
        )
    )
    await session.commit()

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                ImpactAssessment(
                    cluster_id=cluster.id,
                    user_id=user_id,
                    portfolio_id=pf.id,  # same triple
                    mechanism="m" * 60,
                    confidence=Decimal("0.7"),
                    falsifiability="f" * 30,
                    citations=[_sample_citation()],
                    affected_positions=[str(uuid.uuid4())],
                )
            )
            await session.flush()


async def test_confidence_check_constraint(session: AsyncSession):
    cluster = await _mk_cluster(session)
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                ImpactAssessment(
                    cluster_id=cluster.id,
                    user_id=user_id,
                    portfolio_id=pf.id,
                    mechanism="m" * 60,
                    confidence=Decimal("1.20"),  # invalid
                    falsifiability="f" * 30,
                    citations=[_sample_citation()],
                    affected_positions=[str(uuid.uuid4())],
                )
            )
            await session.flush()


async def test_timeframe_check_constraint_allows_null_and_1_to_365(session: AsyncSession):
    cluster = await _mk_cluster(session)
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)

    # Null timeframe is OK.
    session.add(
        ImpactAssessment(
            cluster_id=cluster.id,
            user_id=user_id,
            portfolio_id=pf.id,
            mechanism="m" * 60,
            confidence=Decimal("0.5"),
            timeframe_days=None,
            falsifiability="f" * 30,
            citations=[_sample_citation()],
            affected_positions=[str(uuid.uuid4())],
        )
    )
    await session.commit()

    # 400-day timeframe rejected. Second portfolio must be inactive — the
    # partial unique index (`idx_portfolios_user_active`) permits at most one
    # active portfolio per user.
    other_pf = Portfolio(user_id=user_id, name=f"pf2-{uuid.uuid4().hex[:6]}", is_active=False)
    session.add(other_pf)
    await session.commit()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                ImpactAssessment(
                    cluster_id=cluster.id,
                    user_id=user_id,
                    portfolio_id=other_pf.id,
                    mechanism="m" * 60,
                    confidence=Decimal("0.5"),
                    timeframe_days=400,
                    falsifiability="f" * 30,
                    citations=[_sample_citation()],
                    affected_positions=[str(uuid.uuid4())],
                )
            )
            await session.flush()


async def test_cluster_delete_cascades(session: AsyncSession):
    cluster = await _mk_cluster(session)
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    session.add(
        ImpactAssessment(
            cluster_id=cluster.id,
            user_id=user_id,
            portfolio_id=pf.id,
            mechanism="m" * 60,
            confidence=Decimal("0.5"),
            falsifiability="f" * 30,
            citations=[_sample_citation()],
            affected_positions=[str(uuid.uuid4())],
        )
    )
    await session.commit()

    await session.delete(cluster)
    await session.commit()
    session.expire_all()

    assert (await session.execute(select(ImpactAssessment))).scalars().all() == []


async def test_portfolio_delete_cascades(session: AsyncSession):
    cluster = await _mk_cluster(session)
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    session.add(
        ImpactAssessment(
            cluster_id=cluster.id,
            user_id=user_id,
            portfolio_id=pf.id,
            mechanism="m" * 60,
            confidence=Decimal("0.5"),
            falsifiability="f" * 30,
            citations=[_sample_citation()],
            affected_positions=[str(uuid.uuid4())],
        )
    )
    await session.commit()

    await session.delete(pf)
    await session.commit()
    session.expire_all()

    assert (await session.execute(select(ImpactAssessment))).scalars().all() == []


# --- Pydantic wire-shape validation ----------------------------------------


def test_impact_payload_rejects_empty_citations():
    with pytest.raises(ValidationError):
        ImpactAssessmentPayload(
            mechanism="x" * 60,
            confidence=0.5,
            falsifiability="f" * 30,
            citations=[],  # violates min_length=1
            affected_positions=[uuid.uuid4()],
        )


def test_impact_payload_rejects_empty_affected_positions():
    with pytest.raises(ValidationError):
        ImpactAssessmentPayload(
            mechanism="x" * 60,
            confidence=0.5,
            falsifiability="f" * 30,
            citations=[Citation(**_sample_citation())],
            affected_positions=[],  # violates min_length=1
        )


def test_impact_payload_bounds_confidence_and_timeframe():
    ok = ImpactAssessmentPayload(
        mechanism="x" * 60,
        confidence=0.5,
        timeframe_days=90,
        falsifiability="f" * 30,
        citations=[Citation(**_sample_citation())],
        affected_positions=[uuid.uuid4()],
    )
    assert ok.confidence == 0.5

    with pytest.raises(ValidationError):
        ImpactAssessmentPayload(
            mechanism="x" * 60,
            confidence=1.5,
            falsifiability="f" * 30,
            citations=[Citation(**_sample_citation())],
            affected_positions=[uuid.uuid4()],
        )
    with pytest.raises(ValidationError):
        ImpactAssessmentPayload(
            mechanism="x" * 60,
            confidence=0.5,
            timeframe_days=400,
            falsifiability="f" * 30,
            citations=[Citation(**_sample_citation())],
            affected_positions=[uuid.uuid4()],
        )


def test_historical_analog_similarity_bounded():
    ok = HistoricalAnalog(
        event_description="Fed rate cut March 2020",
        when=date(2020, 3, 15),
        outcome_description="SPX +6% over 5 sessions.",
        similarity_score=0.82,
    )
    assert ok.similarity_score == 0.82
    with pytest.raises(ValidationError):
        HistoricalAnalog(
            event_description="x",
            when=date(2020, 3, 15),
            outcome_description="y",
            similarity_score=1.5,
        )


def test_citation_quote_max_length():
    with pytest.raises(ValidationError):
        Citation(
            source="r",
            url="https://x.example",
            title="t",
            quote="q" * 301,
        )


# --- Migration-level check: citations must be non-empty --------------------


def test_migration_rejects_empty_citations(tmp_path, monkeypatch):
    """Direct run of the alembic chain to head must enforce the citations CHECK.

    env.py resolves the DB URL from `DATABASE_URL` (or `Config.DATABASE_URL`),
    NOT from `alembic_cfg.set_main_option` — the ini override is overwritten
    by env.py at startup. So we set the env var for the duration of the test.

    Side effect: env.py calls `fileConfig(alembic.ini)`, which disables every
    already-created named logger (fileConfig's default behavior). Later tests
    that use caplog on those loggers would then see no records. We re-enable
    everything at the end of the test to keep the side effect scoped.
    """
    import logging

    db_path = tmp_path / "imp01.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)

    alembic_cfg = AlembicConfig(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
    for name in list(logging.root.manager.loggerDict):
        logging.getLogger(name).disabled = False

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            # Skip FK checks so this insert only tests the CHECK constraint.
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            with pytest.raises(Exception) as excinfo:
                conn.execute(
                    text(
                        "INSERT INTO impact_assessments "
                        "(id, cluster_id, user_id, portfolio_id, mechanism, confidence, "
                        "falsifiability, citations, historical_analogs, affected_positions) "
                        "VALUES (:id, :cid, :uid, :pid, :m, 0.5, :f, '[]', '[]', '[]')"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "cid": str(uuid.uuid4()),
                        "uid": str(uuid.uuid4()),
                        "pid": str(uuid.uuid4()),
                        "m": "m" * 60,
                        "f": "f" * 30,
                    },
                )
            msg = str(excinfo.value)
            assert (
                "ck_impact_assessments_citations_nonempty" in msg
                or "CHECK" in msg.upper()
            )
    finally:
        engine.dispose()
