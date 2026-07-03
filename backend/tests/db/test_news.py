"""ING-01 acceptance: news schema round-trip, unique url_hash prevents dupes."""
from __future__ import annotations

import tempfile
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
from app.db.models import IngestRun, NewsCluster, NewsItem  # noqa: F401


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


async def test_news_item_insert_and_unique_url_hash(session: AsyncSession):
    now = datetime.now(timezone.utc)
    cluster = NewsCluster(
        canonical_title="Fed hikes 25bps",
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=["SPY", "TLT"],
        entity_topics=["monetary policy"],
        authority_score=Decimal("0.9"),
        novelty_score=Decimal("1.0"),
    )
    session.add(cluster)
    await session.flush()

    item = NewsItem(
        cluster_id=cluster.id,
        source="newsapi",
        source_id="abc-123",
        url="https://reuters.example/1",
        url_hash="hash-1",
        title="Fed hikes 25bps",
        body="…",
        published_at=now,
    )
    session.add(item)
    await session.commit()

    # Duplicate url_hash → IntegrityError
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                NewsItem(
                    source="newsapi",
                    url="https://reuters.example/1-mirror",
                    url_hash="hash-1",  # same hash
                    title="mirror",
                    published_at=now,
                )
            )
            await session.flush()


async def test_source_check_constraint(session: AsyncSession):
    now = datetime.now(timezone.utc)
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                NewsItem(
                    source="twitter",  # not in the allow-list
                    url="https://x.example/1",
                    url_hash="hash-x",
                    title="",
                    published_at=now,
                )
            )
            session.add_all([])
            # `title` is nullable=False; add a title to isolate the source failure
            session.expunge_all()
            session.add(
                NewsItem(
                    source="twitter",
                    url="https://x.example/1",
                    url_hash="hash-x",
                    title="tweet",
                    published_at=now,
                )
            )
            await session.flush()


async def test_cluster_delete_sets_item_cluster_id_null(session: AsyncSession):
    now = datetime.now(timezone.utc)
    cluster = NewsCluster(
        canonical_title="Oil spikes",
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=["XOM", "USO"],
        entity_topics=["energy"],
    )
    session.add(cluster)
    await session.flush()
    item = NewsItem(
        cluster_id=cluster.id,
        source="rss",
        url="https://oil.example/1",
        url_hash="hash-oil",
        title="Oil spikes",
        published_at=now,
    )
    session.add(item)
    await session.commit()

    await session.delete(cluster)
    await session.commit()
    session.expire_all()  # force a re-read; expire_on_commit=False in fixture

    fresh = (
        await session.execute(select(NewsItem).where(NewsItem.url_hash == "hash-oil"))
    ).scalar_one()
    assert fresh.cluster_id is None


async def test_ingest_run_row(session: AsyncSession):
    now = datetime.now(timezone.utc)
    run = IngestRun(
        source="newsapi",
        started_at=now,
        finished_at=now,
        items_fetched=100,
        items_new=42,
        items_deduped=58,
    )
    session.add(run)
    await session.commit()
    got = (await session.execute(select(IngestRun))).scalar_one()
    assert got.items_new == 42
