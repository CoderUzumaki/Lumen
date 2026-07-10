"""REL-02 acceptance: Fed→AAPL passes; niche pharma→tech portfolio drops."""
from __future__ import annotations

import math
import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import chromadb
import pytest_asyncio
from chromadb.config import Settings
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.db.vectorstore as vs
from app.agents.relevance.prefilter import run_prefilter
from app.db.base import Base
from app.db.models import (  # noqa: F401 register with Base.metadata
    NewsCluster,
    NewsItem,
    Portfolio,
    Position,
    RelevanceScore,
    Theme,
)
from app.utils.embeddings import EmbeddingClient


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class _FakeEmbed(EmbeddingClient):
    """Deterministic embeddings modeling `Fed ↔ equities are semantically close`.

    Dim 0 = "equities/fed" axis. Dim 1 = "pharma" axis. Dim 2 = residual.
    """

    async def embed(self, texts):
        rows: list[list[float]] = []
        for t in texts:
            lo = t.lower()
            if "pharma" in lo:
                rows.append(_unit([0.0, 1.0, 0.0]))
            elif "fed" in lo or "equity" in lo or "aapl" in lo or "nvda" in lo:
                rows.append(_unit([1.0, 0.0, 0.1]))
            else:
                rows.append(_unit([0.0, 0.0, 1.0]))
        return rows


@pytest_asyncio.fixture
async def env() -> AsyncIterator[tuple[AsyncSession, vs.VectorStore, vs.VectorStore]]:
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    chroma_path = Path(tempfile.mkdtemp(prefix="lumen-test-chroma-"))
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _):  # noqa: ARG001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    chroma_client = chromadb.PersistentClient(
        path=str(chroma_path), settings=Settings(anonymized_telemetry=False)
    )
    original = vs._client
    vs._client = chroma_client
    vs.init_collections(client=chroma_client)
    news_store = vs.VectorStore("news_items", client=chroma_client)
    themes_store = vs.VectorStore("themes", client=chroma_client)

    async with factory() as session:
        yield session, news_store, themes_store

    vs._client = original
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass
    import shutil
    shutil.rmtree(chroma_path, ignore_errors=True)


async def _seed_cluster_with_item(
    session: AsyncSession,
    news_store: vs.VectorStore,
    *,
    title: str,
    vec: list[float],
    source: str = "newsapi",
) -> NewsCluster:
    now = datetime.now(timezone.utc)
    cluster = NewsCluster(
        canonical_title=title,
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=[],
        entity_topics=[],
        member_sources=[source],
    )
    session.add(cluster)
    await session.flush()

    item = NewsItem(
        cluster_id=cluster.id,
        source=source,
        source_id=None,
        url=f"https://example.com/{uuid.uuid4().hex[:8]}",
        url_hash=uuid.uuid4().hex,
        title=title,
        body=title,
        published_at=now,
    )
    session.add(item)
    await session.commit()
    news_store.upsert(
        ids=[str(item.id)],
        embeddings=[vec],
        metadatas=[
            {
                "cluster_id": str(cluster.id),
                "source": source,
                "published_at_iso": now.isoformat(),
            }
        ],
        documents=[title],
    )
    return cluster


async def _seed_portfolio(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    tickers: list[str],
) -> Portfolio:
    pf = Portfolio(user_id=user_id, name=f"pf-{uuid.uuid4().hex[:6]}", is_active=True)
    session.add(pf)
    await session.flush()
    for t in tickers:
        session.add(
            Position(
                portfolio_id=pf.id,
                ticker=t,
                asset_type="equity",
                currency="USD",
                exchange="NASDAQ",
            )
        )
    await session.commit()
    return pf


async def test_fed_cluster_and_aapl_portfolio_passes_with_aapl_candidate(env):
    session, news_store, themes_store = env
    user_id = uuid.uuid4()

    cluster = await _seed_cluster_with_item(
        session,
        news_store,
        title="Fed hikes rates by 25bps",
        vec=_unit([1.0, 0.0, 0.1]),
    )
    pf = await _seed_portfolio(session, user_id, tickers=["AAPL"])
    aapl = (
        await session.execute(
            select(Position).where(Position.portfolio_id == pf.id)
        )
    ).scalars().one()

    result = await run_prefilter(
        cluster_id=cluster.id,
        portfolio_id=pf.id,
        session=session,
        news_store=news_store,
        themes_store=themes_store,
        embed=_FakeEmbed(),
    )

    assert result.passed is True
    assert result.max_similarity > 0.35
    assert aapl.id in result.candidate_position_ids


async def test_pharma_cluster_and_tech_portfolio_drops(env):
    session, news_store, themes_store = env
    user_id = uuid.uuid4()

    cluster = await _seed_cluster_with_item(
        session,
        news_store,
        title="Niche pharma FDA approval",
        vec=_unit([0.0, 1.0, 0.0]),
    )
    pf = await _seed_portfolio(session, user_id, tickers=["NVDA", "AAPL"])

    result = await run_prefilter(
        cluster_id=cluster.id,
        portfolio_id=pf.id,
        session=session,
        news_store=news_store,
        themes_store=themes_store,
        embed=_FakeEmbed(),
    )

    assert result.passed is False
    assert result.max_similarity < 0.35

    row = (
        await session.execute(
            select(RelevanceScore).where(
                RelevanceScore.cluster_id == cluster.id,
                RelevanceScore.portfolio_id == pf.id,
            )
        )
    ).scalar_one()
    assert row.stage == "prefilter"
    assert row.touched_position_ids == []
    assert row.touched_theme_ids == []
    assert row.score < Decimal("0.35")


async def test_theme_stored_vector_used(env):
    """A theme whose stored vector is close to the cluster passes prefilter."""
    session, news_store, themes_store = env
    user_id = uuid.uuid4()

    cluster = await _seed_cluster_with_item(
        session,
        news_store,
        title="Fed policy shift",
        vec=_unit([1.0, 0.0, 0.0]),
    )
    # Portfolio has ONLY a theme; no positions.
    pf = await _seed_portfolio(session, user_id, tickers=[])
    theme = Theme(
        user_id=user_id,
        description="US monetary policy",
        weight=Decimal("0.90"),
    )
    session.add(theme)
    await session.commit()
    themes_store.upsert(
        ids=[str(theme.id)],
        embeddings=[_unit([1.0, 0.0, 0.0])],  # aligned with the Fed vector
        metadatas=[{"user_id": str(user_id), "description": theme.description}],
    )

    result = await run_prefilter(
        cluster_id=cluster.id,
        portfolio_id=pf.id,
        session=session,
        news_store=news_store,
        themes_store=themes_store,
        embed=_FakeEmbed(),
    )

    assert result.passed is True
    assert theme.id in result.candidate_theme_ids


async def test_cluster_with_no_embeddings_defers_to_classifier(env):
    """Cluster exists in DB but no Chroma vectors — prefilter should pass."""
    session, news_store, themes_store = env
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    cluster = NewsCluster(
        canonical_title="Nothing indexed yet",
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=[],
        entity_topics=[],
        member_sources=[],
    )
    session.add(cluster)
    await session.commit()

    pf = await _seed_portfolio(session, user_id, tickers=["AAPL"])

    result = await run_prefilter(
        cluster_id=cluster.id,
        portfolio_id=pf.id,
        session=session,
        news_store=news_store,
        themes_store=themes_store,
        embed=_FakeEmbed(),
    )

    assert result.passed is True
    assert result.max_similarity == 0.0
    # No row persisted (would be a stage='prefilter' row) — defer to classifier.
    count = (
        (
            await session.execute(
                select(RelevanceScore).where(RelevanceScore.cluster_id == cluster.id)
            )
        )
        .scalars()
        .all()
    )
    assert list(count) == []


async def test_threshold_boundary_at_zero(env):
    """`threshold=0` means everything passes."""
    session, news_store, themes_store = env
    user_id = uuid.uuid4()

    cluster = await _seed_cluster_with_item(
        session,
        news_store,
        title="Random tokens",
        vec=_unit([0.5, 0.5, 0.5]),
    )
    pf = await _seed_portfolio(session, user_id, tickers=["AAPL"])

    result = await run_prefilter(
        cluster_id=cluster.id,
        portfolio_id=pf.id,
        session=session,
        news_store=news_store,
        themes_store=themes_store,
        embed=_FakeEmbed(),
        threshold=0.0,
    )
    assert result.passed is True
    assert result.max_similarity >= 0.0
