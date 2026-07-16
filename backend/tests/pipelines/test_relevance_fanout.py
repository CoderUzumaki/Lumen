"""REL-05 acceptance: fan-out worker persists ≤ 150 rows for 50×3 and re-runs idempotently."""
from __future__ import annotations

import asyncio
import logging
import math
import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
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
from app.db.base import Base
from app.db.models import (  # noqa: F401 register with Base.metadata
    NewsCluster,
    NewsItem,
    Portfolio,
    Position,
    RelevanceScore,
    Theme,
)
from app.pipelines.relevance_fanout import run_fanout
from app.utils.embeddings import EmbeddingClient
from app.utils.llm import LLMClient, LLMResponse


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class _FakeEmbed(EmbeddingClient):
    """Simple deterministic embed: everything lands near the equities axis."""

    async def embed(self, texts):
        rows = []
        for _ in texts:
            rows.append(_unit([1.0, 0.0, 0.1]))
        return rows


class _CountingLLM(LLMClient):
    """Returns a canned verdict; counts .complete() invocations across concurrent tasks."""

    def __init__(self, verdict: RelevanceVerdict) -> None:
        super().__init__(http_client=AsyncMock())
        self._verdict = verdict
        self._calls = 0
        self._lock = asyncio.Lock()

    async def complete(self, messages, **kwargs):  # type: ignore[override]
        async with self._lock:
            self._calls += 1
        return LLMResponse(
            content=self._verdict.model_dump_json(),
            parsed=self._verdict,
            model="fake",
            tier=kwargs.get("tier", "fast"),
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
        )

    @property
    def calls(self) -> int:
        return self._calls


@pytest_asyncio.fixture
async def env() -> AsyncIterator[
    tuple[
        async_sessionmaker[AsyncSession],
        AsyncSession,
        vs.VectorStore,
        vs.VectorStore,
    ]
]:
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
        yield factory, session, news_store, themes_store

    vs._client = original
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass
    import shutil
    shutil.rmtree(chroma_path, ignore_errors=True)


async def _seed_cluster(
    session: AsyncSession, news_store: vs.VectorStore, *, title: str, vec: list[float]
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


async def _seed_active_portfolio(session: AsyncSession, user_id: uuid.UUID) -> Portfolio:
    pf = Portfolio(user_id=user_id, name=f"pf-{uuid.uuid4().hex[:6]}", is_active=True)
    session.add(pf)
    await session.flush()
    session.add(
        Position(
            portfolio_id=pf.id,
            ticker="AAPL",
            asset_type="equity",
            currency="USD",
            exchange="NASDAQ",
        )
    )
    await session.commit()
    return pf


async def test_fanout_50_clusters_3_users_yields_at_most_150_rows_and_reruns_zero(env):
    """Acceptance: 50 clusters × 3 users → ≤150 rows; re-running yields 0 new rows."""
    factory, session, news_store, themes_store = env

    for _ in range(3):
        await _seed_active_portfolio(session, uuid.uuid4())
    cluster_ids: list[uuid.UUID] = []
    for i in range(50):
        c = await _seed_cluster(
            session, news_store, title=f"Event {i}", vec=_unit([1.0, 0.0, 0.1])
        )
        cluster_ids.append(c.id)

    verdict = RelevanceVerdict(
        score=0.65, touched_positions=[], touched_themes=[], rationale="mechanism"
    )
    llm = _CountingLLM(verdict)

    summary = await run_fanout(
        session_factory=factory,
        news_store=news_store,
        themes_store=themes_store,
        embed=_FakeEmbed(),
        llm=llm,
        cluster_ids=cluster_ids,
        concurrency=10,
    )

    assert summary.tasks == 150
    assert summary.errors == 0

    async with factory() as s2:
        total = (
            await s2.execute(select(RelevanceScore))
        ).scalars().all()
    assert len(list(total)) <= 150
    assert len(list(total)) == 150

    # Re-run: idempotency check.
    llm_before = llm.calls
    summary2 = await run_fanout(
        session_factory=factory,
        news_store=news_store,
        themes_store=themes_store,
        embed=_FakeEmbed(),
        llm=llm,
        cluster_ids=cluster_ids,
        concurrency=10,
    )
    assert summary2.tasks == 150
    assert summary2.cache_hits == 150
    assert llm.calls == llm_before  # No new LLM calls on the second pass.

    async with factory() as s3:
        after = (await s3.execute(select(RelevanceScore))).scalars().all()
    assert len(list(after)) == 150  # ← zero new rows


async def test_fanout_since_window_only_scores_clusters_touched_after_since(env):
    """The `since` discovery path picks up only clusters with last_seen_at >= since."""
    factory, session, news_store, themes_store = env
    pf = await _seed_active_portfolio(session, uuid.uuid4())

    # Old cluster: last_seen_at well in the past.
    old = NewsCluster(
        canonical_title="Old event",
        first_seen_at=datetime.now(timezone.utc) - timedelta(hours=2),
        last_seen_at=datetime.now(timezone.utc) - timedelta(hours=2),
        entity_tickers=[],
        entity_topics=[],
        member_sources=["newsapi"],
    )
    session.add(old)
    await session.commit()

    boundary = datetime.now(timezone.utc)
    # Fresh cluster: last_seen_at >= boundary.
    fresh = await _seed_cluster(
        session, news_store, title="Fresh event", vec=_unit([1.0, 0.0, 0.1])
    )

    llm = _CountingLLM(
        RelevanceVerdict(
            score=0.7, touched_positions=[], touched_themes=[], rationale="x"
        )
    )

    summary = await run_fanout(
        session_factory=factory,
        news_store=news_store,
        themes_store=themes_store,
        embed=_FakeEmbed(),
        llm=llm,
        since=boundary,
    )

    # Only the fresh cluster is in scope; only pf is active → 1 task.
    assert summary.tasks == 1
    assert summary.cluster_ids == [fresh.id]
    # Old cluster gets no row; fresh cluster gets one.
    async with factory() as s2:
        rows = (await s2.execute(select(RelevanceScore))).scalars().all()
    rows = list(rows)
    assert len(rows) == 1
    assert rows[0].cluster_id == fresh.id
    assert rows[0].portfolio_id == pf.id


async def test_fanout_inactive_portfolios_are_skipped(env):
    factory, session, news_store, themes_store = env
    # Active portfolio.
    _active = await _seed_active_portfolio(session, uuid.uuid4())
    # Inactive portfolio for another user.
    inactive = Portfolio(user_id=uuid.uuid4(), name="Retired", is_active=False)
    session.add(inactive)
    await session.commit()

    cluster = await _seed_cluster(
        session, news_store, title="Fed", vec=_unit([1.0, 0.0, 0.1])
    )
    llm = _CountingLLM(
        RelevanceVerdict(
            score=0.5, touched_positions=[], touched_themes=[], rationale="x"
        )
    )
    summary = await run_fanout(
        session_factory=factory,
        news_store=news_store,
        themes_store=themes_store,
        embed=_FakeEmbed(),
        llm=llm,
        cluster_ids=[cluster.id],
    )
    assert summary.tasks == 1  # only the active portfolio
    async with factory() as s2:
        rows = (await s2.execute(select(RelevanceScore))).scalars().all()
    assert len(list(rows)) == 1


async def test_fanout_respects_concurrency_bound(env):
    """LLM calls run concurrently but never exceed `concurrency` in flight."""
    factory, session, news_store, themes_store = env
    # 4 active portfolios so we have a real fan for a single cluster.
    for _ in range(4):
        await _seed_active_portfolio(session, uuid.uuid4())
    cluster = await _seed_cluster(
        session, news_store, title="Event", vec=_unit([1.0, 0.0, 0.1])
    )

    max_in_flight = 0
    in_flight = 0
    lock = asyncio.Lock()
    verdict = RelevanceVerdict(
        score=0.5, touched_positions=[], touched_themes=[], rationale="x"
    )

    class _TrackingLLM(LLMClient):
        def __init__(self) -> None:
            super().__init__(http_client=AsyncMock())

        async def complete(self, messages, **kwargs):  # type: ignore[override]
            nonlocal in_flight, max_in_flight
            async with lock:
                in_flight += 1
                if in_flight > max_in_flight:
                    max_in_flight = in_flight
            # Yield to other tasks so they can pile up under the semaphore.
            await asyncio.sleep(0.05)
            async with lock:
                in_flight -= 1
            return LLMResponse(
                content=verdict.model_dump_json(),
                parsed=verdict,
                model="fake",
                tier=kwargs.get("tier", "fast"),
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=0,
            )

    await run_fanout(
        session_factory=factory,
        news_store=news_store,
        themes_store=themes_store,
        embed=_FakeEmbed(),
        llm=_TrackingLLM(),
        cluster_ids=[cluster.id],
        concurrency=2,
    )
    assert max_in_flight <= 2
    assert max_in_flight >= 1  # sanity: at least one call actually ran


async def test_fanout_logs_per_cluster_cost_line(env, caplog):
    factory, session, news_store, themes_store = env
    await _seed_active_portfolio(session, uuid.uuid4())
    cluster = await _seed_cluster(
        session, news_store, title="Event", vec=_unit([1.0, 0.0, 0.1])
    )
    verdict = RelevanceVerdict(
        score=0.5, touched_positions=[], touched_themes=[], rationale="x"
    )
    llm = _CountingLLM(verdict)
    with caplog.at_level(logging.INFO, logger="app.pipelines.relevance_fanout"):
        await run_fanout(
            session_factory=factory,
            news_store=news_store,
            themes_store=themes_store,
            embed=_FakeEmbed(),
            llm=llm,
            cluster_ids=[cluster.id],
        )
    per_cluster_lines = [r for r in caplog.records if "fanout_cluster" in r.getMessage()]
    assert per_cluster_lines, "expected at least one per-cluster cost log line"
    msg = per_cluster_lines[0].getMessage()
    assert f"cluster={cluster.id}" in msg
    assert "est_tokens=" in msg


async def test_fanout_requires_cluster_ids_or_since(env):
    import pytest

    factory, session, news_store, themes_store = env
    llm = _CountingLLM(
        RelevanceVerdict(
            score=0.5, touched_positions=[], touched_themes=[], rationale="x"
        )
    )
    with pytest.raises(ValueError):
        await run_fanout(
            session_factory=factory,
            news_store=news_store,
            themes_store=themes_store,
            embed=_FakeEmbed(),
            llm=llm,
        )
