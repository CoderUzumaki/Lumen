"""ING-08 acceptance: persist idempotency + Chroma indexing."""
from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from datetime import datetime, timezone
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
from app.db.models import NewsItem  # noqa: F401 register with Base.metadata
from app.pipelines.normalizer import NormalizedItem
from app.pipelines.persist import persist
from app.utils.embeddings import EmbeddingClient


class _FakeEmbed(EmbeddingClient):
    async def embed(self, texts):
        # 3-dim vector per text — content doesn't matter for persist tests.
        return [[float(i), 0.0, 0.0] for i, _ in enumerate(texts)]


@pytest_asyncio.fixture
async def env() -> AsyncIterator[tuple[AsyncSession, _FakeEmbed, vs.VectorStore, chromadb.PersistentClient]]:
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
    embed = _FakeEmbed()

    async with factory() as session:
        yield session, embed, store, chroma_client

    vs._client = original_vs_client
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass
    import shutil
    shutil.rmtree(chroma_path, ignore_errors=True)


def _mk_norm(url_suffix: str, hash_suffix: str = None) -> NormalizedItem:
    return NormalizedItem(
        source="newsapi",
        source_id=None,
        url=f"https://reuters.com/{url_suffix}",
        url_hash=hash_suffix or f"hash-{url_suffix}",
        title=f"Story about {url_suffix}",
        body=f"body of {url_suffix}",
        published_at=datetime(2026, 7, 3, 12, tzinfo=timezone.utc),
        raw_payload={},
        hints={},
        tickers=[],
    )


async def test_first_persist_inserts_all(env):
    session, embed, store, _ = env
    items = [_mk_norm("a"), _mk_norm("b"), _mk_norm("c")]
    inserted, skipped = await persist(items, session=session, embed=embed, store=store)
    assert inserted == 3
    assert skipped == 0
    assert store.count() == 3


async def test_second_persist_skips_all_duplicates(env):
    session, embed, store, _ = env
    items = [_mk_norm("a"), _mk_norm("b"), _mk_norm("c")]

    first = await persist(items, session=session, embed=embed, store=store)
    assert first == (3, 0)

    # Same list, second call — every url_hash already there.
    second = await persist(items, session=session, embed=embed, store=store)
    assert second == (0, 3)
    # Chroma count is unchanged (upsert on same ids would still be 3 if we
    # re-indexed, but we don't touch Chroma for skipped rows).
    assert store.count() == 3


async def test_persist_indexes_chroma_with_matching_ids(env):
    session, embed, store, chroma = env
    items = [_mk_norm("a"), _mk_norm("b")]
    await persist(items, session=session, embed=embed, store=store)

    # Fetch the row ids the DB assigned; verify Chroma has the same ids.
    rows = (await session.execute(select(NewsItem))).scalars().all()
    db_ids = {str(r.id) for r in rows}
    assert len(db_ids) == 2

    news_col = chroma.get_or_create_collection("news_items")
    chroma_result = news_col.get(include=["metadatas"])
    chroma_ids = set(chroma_result["ids"])
    assert chroma_ids == db_ids

    # Metadata sanity: source and published_at_iso populated.
    for m in chroma_result["metadatas"]:
        assert m["source"] == "newsapi"
        assert m["published_at_iso"].startswith("2026-07-03")


async def test_empty_input_returns_zero_zero(env):
    session, embed, store, _ = env
    assert await persist([], session=session, embed=embed, store=store) == (0, 0)
    assert store.count() == 0


async def test_intra_batch_duplicate_counted_once(env):
    session, embed, store, _ = env
    dup1 = _mk_norm("a")
    dup2 = _mk_norm("a")  # same url_hash
    dup2.title = "Different title but same URL"
    items = [dup1, dup2, _mk_norm("b")]
    inserted, skipped = await persist(items, session=session, embed=embed, store=store)
    assert inserted == 2  # a + b
    assert skipped == 0  # intra-batch dedup, not "existing"
    assert store.count() == 2
