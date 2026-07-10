"""ING-09 acceptance: semantic dedup + clustering."""
from __future__ import annotations

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
from app.db.base import Base
from app.db.models import NewsCluster, NewsItem  # noqa: F401 register
from app.pipelines.clusterer import cluster_item


class _NormalizedVec:
    """Small helper that returns L2-normalized 3-dim vectors."""

    @staticmethod
    def with_marker(fed: float = 0.0, oil: float = 0.0, ai: float = 0.0) -> list[float]:
        import math

        v = [fed, oil, ai]
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]


@pytest_asyncio.fixture
async def env() -> AsyncIterator[tuple[AsyncSession, vs.VectorStore]]:
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
    original_vs_client = vs._client
    vs._client = chroma_client
    vs.init_collections(client=chroma_client)
    store = vs.VectorStore("news_items", client=chroma_client)

    async with factory() as session:
        yield session, store

    vs._client = original_vs_client
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass
    import shutil
    shutil.rmtree(chroma_path, ignore_errors=True)


async def _persist_item(
    session: AsyncSession,
    store: vs.VectorStore,
    *,
    title: str,
    body: str,
    source: str,
    url_hash: str,
    vec: list[float],
    published_at: datetime,
) -> NewsItem:
    """Persist a news item + its Chroma vector — mimics ING-08 without dedup."""
    item = NewsItem(
        id=uuid.uuid4(),
        source=source,
        source_id=None,
        url=f"https://example.com/{url_hash}",
        url_hash=url_hash,
        title=title,
        body=body,
        published_at=published_at,
    )
    session.add(item)
    await session.commit()
    store.upsert(
        ids=[str(item.id)],
        embeddings=[vec],
        metadatas=[
            {
                "cluster_id": "",
                "source": source,
                "published_at_iso": published_at.isoformat(),
            }
        ],
        documents=[title],
    )
    return item


async def test_three_near_duplicates_end_up_in_one_cluster(env):
    session, store = env
    now = datetime(2026, 7, 3, 12, tzinfo=timezone.utc)

    # Three articles about the Fed hike from different sources, very close in
    # embedding space.
    a = await _persist_item(
        session,
        store,
        title="Fed raises rates",
        body="The Federal Reserve raised rates by 25bps today.",
        source="newsapi",
        url_hash="fed-a",
        vec=_NormalizedVec.with_marker(fed=1.0),
        published_at=now,
    )
    b = await _persist_item(
        session,
        store,
        title="Federal Reserve hikes 25bps",
        body="Rates up a quarter point per the FOMC.",
        source="rss",
        url_hash="fed-b",
        vec=_NormalizedVec.with_marker(fed=0.98, ai=0.01),
        published_at=now,
    )
    c = await _persist_item(
        session,
        store,
        title="FOMC lifts rate",
        body="Central bank tightens further.",
        source="gdelt",
        url_hash="fed-c",
        vec=_NormalizedVec.with_marker(fed=0.99, oil=0.005),
        published_at=now,
    )

    cid_a = await cluster_item(a, session=session, store=store, tickers=["SPY"], now=now)
    cid_b = await cluster_item(b, session=session, store=store, tickers=["SPY"], now=now)
    cid_c = await cluster_item(c, session=session, store=store, tickers=["SPY"], now=now)

    assert cid_a == cid_b == cid_c

    cluster = (await session.execute(select(NewsCluster).where(NewsCluster.id == cid_a))).scalar_one()
    assert set(cluster.member_sources) == {"newsapi", "rss", "gdelt"}
    # authority = max(newsapi=0.60, rss=0.70, gdelt=0.50) = 0.70
    assert cluster.authority_score == Decimal("0.70")


async def test_unrelated_articles_end_up_in_different_clusters(env):
    session, store = env
    now = datetime(2026, 7, 3, 12, tzinfo=timezone.utc)

    fed = await _persist_item(
        session,
        store,
        title="Fed hikes rates",
        body="quarter-point tightening",
        source="newsapi",
        url_hash="fed",
        vec=_NormalizedVec.with_marker(fed=1.0),
        published_at=now,
    )
    oil = await _persist_item(
        session,
        store,
        title="Oil rallies past $100",
        body="Brent surges on OPEC signals",
        source="rss",
        url_hash="oil",
        vec=_NormalizedVec.with_marker(oil=1.0),
        published_at=now,
    )

    cid_fed = await cluster_item(fed, session=session, store=store, now=now)
    cid_oil = await cluster_item(oil, session=session, store=store, now=now)

    assert cid_fed != cid_oil


async def test_similarity_below_threshold_gets_new_cluster(env):
    """Neighbor exists but below CLUSTER_SIMILARITY_THRESHOLD → new cluster."""
    session, store = env
    now = datetime(2026, 7, 3, 12, tzinfo=timezone.utc)

    a = await _persist_item(
        session,
        store,
        title="Story one",
        body="body one",
        source="newsapi",
        url_hash="a",
        vec=_NormalizedVec.with_marker(fed=1.0),
        published_at=now,
    )
    # Vector orthogonal to `a` — cosine similarity is 0.
    b = await _persist_item(
        session,
        store,
        title="Story two",
        body="body two",
        source="gdelt",
        url_hash="b",
        vec=_NormalizedVec.with_marker(oil=1.0),
        published_at=now,
    )

    cid_a = await cluster_item(a, session=session, store=store, now=now)
    # Force a permissive threshold to see what happens with dissimilar neighbor.
    cid_b = await cluster_item(b, session=session, store=store, now=now, threshold=0.87)
    assert cid_a != cid_b


async def test_second_article_beyond_48h_starts_new_cluster(env):
    """Neighbor is too old — 48h window excludes it."""
    session, store = env
    old = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    now = datetime(2026, 7, 3, 13, tzinfo=timezone.utc)  # >48h later

    a = await _persist_item(
        session,
        store,
        title="Fed hikes",
        body="quarter point",
        source="newsapi",
        url_hash="a",
        vec=_NormalizedVec.with_marker(fed=1.0),
        published_at=old,
    )
    b = await _persist_item(
        session,
        store,
        title="Fed hikes again",
        body="another quarter point",
        source="rss",
        url_hash="b",
        vec=_NormalizedVec.with_marker(fed=1.0),
        published_at=now,
    )

    cid_a = await cluster_item(a, session=session, store=store, now=old)
    cid_b = await cluster_item(b, session=session, store=store, now=now)
    assert cid_a != cid_b


async def test_novelty_score_decays_with_members(env):
    """Novelty = clamp(1 - count/10, 0.1, 1.0)."""
    session, store = env
    now = datetime(2026, 7, 3, 12, tzinfo=timezone.utc)

    items: list[NewsItem] = []
    for i in range(5):
        it = await _persist_item(
            session,
            store,
            title=f"Fed story {i}",
            body="body",
            source="rss",
            url_hash=f"fed-{i}",
            vec=_NormalizedVec.with_marker(fed=1.0),
            published_at=now,
        )
        items.append(it)

    cid = None
    for it in items:
        cid = await cluster_item(it, session=session, store=store, now=now)

    cluster = (await session.execute(select(NewsCluster).where(NewsCluster.id == cid))).scalar_one()
    # 5 members ⇒ novelty = 1 - 5/10 = 0.5
    assert cluster.novelty_score == Decimal("0.50")


async def test_chroma_metadata_gets_cluster_id_stamped(env):
    session, store = env
    now = datetime(2026, 7, 3, 12, tzinfo=timezone.utc)
    a = await _persist_item(
        session,
        store,
        title="story a",
        body="body a",
        source="newsapi",
        url_hash="a",
        vec=_NormalizedVec.with_marker(fed=1.0),
        published_at=now,
    )
    cid = await cluster_item(a, session=session, store=store, now=now)
    got = store.get(ids=[str(a.id)], include=["metadatas"])
    assert got["metadatas"][0]["cluster_id"] == str(cid)
