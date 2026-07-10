"""REL-01 acceptance: relevance_scores schema, unique upsert, cascades."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
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

from app.db.base import Base
from app.db.models import (  # noqa: F401 register
    NewsCluster,
    Portfolio,
    RelevanceScore,
)


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
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


async def test_insert_and_unique_constraint(session: AsyncSession):
    cluster = await _mk_cluster(session)
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)

    row = RelevanceScore(
        cluster_id=cluster.id,
        user_id=user_id,
        portfolio_id=pf.id,
        score=Decimal("0.42"),
        touched_position_ids=[],
        touched_theme_ids=[],
        stage="prefilter",
    )
    session.add(row)
    await session.commit()

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                RelevanceScore(
                    cluster_id=cluster.id,
                    user_id=user_id,
                    portfolio_id=pf.id,  # same triple
                    score=Decimal("0.90"),
                    touched_position_ids=[],
                    touched_theme_ids=[],
                    stage="classifier",
                )
            )
            await session.flush()


async def test_score_check_constraint(session: AsyncSession):
    cluster = await _mk_cluster(session)
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                RelevanceScore(
                    cluster_id=cluster.id,
                    user_id=user_id,
                    portfolio_id=pf.id,
                    score=Decimal("1.50"),  # invalid
                    touched_position_ids=[],
                    touched_theme_ids=[],
                    stage="classifier",
                )
            )
            await session.flush()


async def test_stage_check_constraint(session: AsyncSession):
    cluster = await _mk_cluster(session)
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                RelevanceScore(
                    cluster_id=cluster.id,
                    user_id=user_id,
                    portfolio_id=pf.id,
                    score=Decimal("0.5"),
                    touched_position_ids=[],
                    touched_theme_ids=[],
                    stage="magic",  # not in allow-list
                )
            )
            await session.flush()


async def test_cluster_delete_cascades(session: AsyncSession):
    cluster = await _mk_cluster(session)
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)

    session.add(
        RelevanceScore(
            cluster_id=cluster.id,
            user_id=user_id,
            portfolio_id=pf.id,
            score=Decimal("0.7"),
            touched_position_ids=[],
            touched_theme_ids=[],
            stage="classifier",
        )
    )
    await session.commit()

    await session.delete(cluster)
    await session.commit()
    session.expire_all()

    remaining = list(
        (await session.execute(select(RelevanceScore))).scalars().all()
    )
    assert remaining == []


async def test_portfolio_delete_cascades(session: AsyncSession):
    cluster = await _mk_cluster(session)
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)

    session.add(
        RelevanceScore(
            cluster_id=cluster.id,
            user_id=user_id,
            portfolio_id=pf.id,
            score=Decimal("0.7"),
            touched_position_ids=[],
            touched_theme_ids=[],
            stage="classifier",
        )
    )
    await session.commit()

    await session.delete(pf)
    await session.commit()
    session.expire_all()

    assert (
        list((await session.execute(select(RelevanceScore))).scalars().all())
        == []
    )
