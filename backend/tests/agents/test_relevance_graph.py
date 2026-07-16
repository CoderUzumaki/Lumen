"""REL-04 acceptance: LangGraph composition of prefilter + classifier."""
from __future__ import annotations

import math
import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

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
from app.agents.relevance.classifier import RelevanceVerdict
from app.agents.relevance.graph import (
    RELEVANCE_GRAPH,
    score_cluster_for_user,
)
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
from app.utils.llm import LLMClient, LLMResponse


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class _FakeEmbed(EmbeddingClient):
    async def embed(self, texts):
        rows: list[list[float]] = []
        for t in texts:
            lo = t.lower()
            if "pharma" in lo:
                rows.append(_unit([0.0, 1.0, 0.0]))
            elif "fed" in lo or "aapl" in lo:
                rows.append(_unit([1.0, 0.0, 0.1]))
            else:
                rows.append(_unit([0.0, 0.0, 1.0]))
        return rows


class _CountingLLM(LLMClient):
    """LLMClient that returns a canned verdict and counts invocations."""

    def __init__(self, verdict: RelevanceVerdict) -> None:
        super().__init__(http_client=AsyncMock())
        self._verdict = verdict
        self.calls = 0

    async def complete(self, messages, **kwargs):  # type: ignore[override]
        self.calls += 1
        return LLMResponse(
            content=self._verdict.model_dump_json(),
            parsed=self._verdict,
            model="fake",
            tier=kwargs.get("tier", "fast"),
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
        )


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


async def _seed_cluster(
    session: AsyncSession,
    news_store: vs.VectorStore,
    *,
    title: str,
    vec: list[float],
) -> NewsCluster:
    now = datetime.now(timezone.utc)
    cluster = NewsCluster(
        canonical_title=title,
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=[],
        entity_topics=[],
        member_sources=["newsapi"],
    )
    session.add(cluster)
    await session.flush()
    item = NewsItem(
        cluster_id=cluster.id,
        source="newsapi",
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
                "source": "newsapi",
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


def test_graph_compiles_at_import():
    """Acceptance: `graph is compilable at import time.`"""
    assert RELEVANCE_GRAPH is not None
    # And the compiled graph exposes ainvoke.
    assert hasattr(RELEVANCE_GRAPH, "ainvoke")


async def test_prefilter_hit_returns_classifier_row(env):
    """Fed cluster + AAPL portfolio → passes prefilter → classifier persists."""
    session, news_store, themes_store = env
    user_id = uuid.uuid4()

    cluster = await _seed_cluster(
        session,
        news_store,
        title="Fed hikes rates 25bps",
        vec=_unit([1.0, 0.0, 0.1]),
    )
    pf = await _seed_portfolio(session, user_id, tickers=["AAPL"])
    aapl = (
        await session.execute(
            select(Position).where(Position.portfolio_id == pf.id)
        )
    ).scalars().one()

    verdict = RelevanceVerdict(
        score=0.75,
        touched_positions=[aapl.id],
        touched_themes=[],
        rationale="Rate hikes compress duration-sensitive equity valuations.",
    )
    llm = _CountingLLM(verdict)

    row = await score_cluster_for_user(
        cluster.id,
        user_id,
        pf.id,
        session=session,
        news_store=news_store,
        themes_store=themes_store,
        embed=_FakeEmbed(),
        llm=llm,
    )

    assert isinstance(row, RelevanceScore)
    assert row.stage == "classifier"
    assert row.score == Decimal("0.75")
    assert row.touched_position_ids == [str(aapl.id)]
    assert llm.calls == 1


async def test_prefilter_short_circuit_returns_prefilter_row_and_skips_llm(env):
    """Pharma cluster + tech portfolio → prefilter drops → classifier never runs."""
    session, news_store, themes_store = env
    user_id = uuid.uuid4()

    cluster = await _seed_cluster(
        session,
        news_store,
        title="Niche pharma FDA denial",
        vec=_unit([0.0, 1.0, 0.0]),
    )
    pf = await _seed_portfolio(session, user_id, tickers=["AAPL"])
    verdict = RelevanceVerdict(
        score=0.99, touched_positions=[], touched_themes=[], rationale="unused"
    )
    llm = _CountingLLM(verdict)

    row = await score_cluster_for_user(
        cluster.id,
        user_id,
        pf.id,
        session=session,
        news_store=news_store,
        themes_store=themes_store,
        embed=_FakeEmbed(),
        llm=llm,
    )

    assert row.stage == "prefilter"
    assert row.score < Decimal("0.35")
    assert llm.calls == 0


async def test_idempotent_second_call_returns_cached_row_without_llm(env):
    """Acceptance: second call for the same key returns the row, no LLM re-invocation."""
    session, news_store, themes_store = env
    user_id = uuid.uuid4()

    cluster = await _seed_cluster(
        session,
        news_store,
        title="Fed statement",
        vec=_unit([1.0, 0.0, 0.1]),
    )
    pf = await _seed_portfolio(session, user_id, tickers=["AAPL"])
    aapl = (
        await session.execute(
            select(Position).where(Position.portfolio_id == pf.id)
        )
    ).scalars().one()
    verdict = RelevanceVerdict(
        score=0.6,
        touched_positions=[aapl.id],
        touched_themes=[],
        rationale="rate mechanism",
    )
    llm = _CountingLLM(verdict)

    first = await score_cluster_for_user(
        cluster.id, user_id, pf.id,
        session=session, news_store=news_store, themes_store=themes_store,
        embed=_FakeEmbed(), llm=llm,
    )
    second = await score_cluster_for_user(
        cluster.id, user_id, pf.id,
        session=session, news_store=news_store, themes_store=themes_store,
        embed=_FakeEmbed(), llm=llm,
    )

    assert first.id == second.id
    assert llm.calls == 1

    # Only one row in the DB for this key.
    count = (
        await session.execute(
            select(RelevanceScore).where(
                RelevanceScore.cluster_id == cluster.id,
                RelevanceScore.portfolio_id == pf.id,
            )
        )
    ).scalars().all()
    assert len(list(count)) == 1


async def test_force_true_re_invokes_and_replaces_row(env):
    """`force=True` deletes the cached row and re-runs the graph."""
    session, news_store, themes_store = env
    user_id = uuid.uuid4()

    cluster = await _seed_cluster(
        session,
        news_store,
        title="Fed presser",
        vec=_unit([1.0, 0.0, 0.1]),
    )
    pf = await _seed_portfolio(session, user_id, tickers=["AAPL"])
    aapl = (
        await session.execute(
            select(Position).where(Position.portfolio_id == pf.id)
        )
    ).scalars().one()
    verdict = RelevanceVerdict(
        score=0.5,
        touched_positions=[aapl.id],
        touched_themes=[],
        rationale="mechanism v1",
    )
    llm = _CountingLLM(verdict)

    first = await score_cluster_for_user(
        cluster.id, user_id, pf.id,
        session=session, news_store=news_store, themes_store=themes_store,
        embed=_FakeEmbed(), llm=llm,
    )
    first_id = first.id
    assert llm.calls == 1

    # Swap in a new verdict; force re-run.
    llm._verdict = RelevanceVerdict(
        score=0.9,
        touched_positions=[aapl.id],
        touched_themes=[],
        rationale="mechanism v2 (stronger)",
    )
    second = await score_cluster_for_user(
        cluster.id, user_id, pf.id,
        session=session, news_store=news_store, themes_store=themes_store,
        embed=_FakeEmbed(), llm=llm, force=True,
    )
    assert llm.calls == 2
    assert second.id != first_id
    assert second.score == Decimal("0.90")
    assert "v2" in (second.rationale or "")

    # And still exactly one row for the key.
    rows = (
        await session.execute(
            select(RelevanceScore).where(
                RelevanceScore.cluster_id == cluster.id,
                RelevanceScore.portfolio_id == pf.id,
            )
        )
    ).scalars().all()
    assert len(list(rows)) == 1
