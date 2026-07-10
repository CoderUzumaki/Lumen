"""ING-10 acceptance: orchestrator run across sources, per-source isolation, health endpoint."""
from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

import chromadb
import pytest_asyncio
from chromadb.config import Settings
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.db.vectorstore as vs
from app.db.base import Base, get_db_session
from app.db.models import IngestRun, NewsItem  # noqa: F401 register
from app.main import app
from app.pipelines.orchestrator import IngestOrchestrator
from app.pipelines.sources.base import BaseSource
from app.schemas.news import NewsItemIn
from app.utils.embeddings import EmbeddingClient


class _FakeSource(BaseSource):
    """Deterministic in-memory source for orchestrator tests."""

    def __init__(self, *, name: str, items: list[NewsItemIn] | None = None, raises: Exception | None = None):
        self.source_name = name
        self._items = items or []
        self._raises = raises

    async def fetch(self, since):  # noqa: ARG002
        if self._raises is not None:
            raise self._raises
        return list(self._items)


class _FakeEmbed(EmbeddingClient):
    """3-dim marker embeddings so clustering behaves deterministically."""

    async def embed(self, texts):
        rows = []
        for t in texts:
            lo = t.lower()
            rows.append(
                [
                    1.0 if "fed" in lo else 0.0,
                    1.0 if "oil" in lo else 0.0,
                    1.0 if "nvda" in lo else 0.0,
                ]
            )
        # normalize to unit vectors
        import math

        norm = []
        for v in rows:
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            norm.append([x / n for x in v])
        return norm


def _mk_news_item(*, source: str, url: str, title: str) -> NewsItemIn:
    return NewsItemIn(
        source=source,
        source_id=None,
        url=url,
        title=title,
        body="body",
        published_at=datetime(2026, 7, 3, 12, tzinfo=timezone.utc),
    )


@pytest_asyncio.fixture
async def env() -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], vs.VectorStore, chromadb.PersistentClient]]:
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
    original_vs = vs._client
    vs._client = chroma_client
    vs.init_collections(client=chroma_client)
    store = vs.VectorStore("news_items", client=chroma_client)

    yield factory, store, chroma_client

    vs._client = original_vs
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass
    import shutil
    shutil.rmtree(chroma_path, ignore_errors=True)


async def test_all_sources_run_and_ingest_runs_rows_created(env):
    factory, store, _ = env
    sources = [
        _FakeSource(
            name="newsapi",
            items=[_mk_news_item(source="newsapi", url="https://a/1", title="Fed hikes")],
        ),
        _FakeSource(
            name="rss",
            items=[_mk_news_item(source="rss", url="https://b/1", title="Oil rallies")],
        ),
    ]
    orchestrator = IngestOrchestrator(
        session_factory=factory,
        embed=_FakeEmbed(),
        store=store,
        source_factory=lambda _tickers: sources,
    )
    summaries = await orchestrator.run(since=datetime(2026, 7, 3, tzinfo=timezone.utc))

    assert {s.source for s in summaries} == {"newsapi", "rss"}
    for s in summaries:
        assert s.error is None
        assert s.items_fetched == 1
        assert s.items_new == 1
        assert s.finished_at is not None

    # Each source has one ingest_runs row.
    async with factory() as session:
        rows = (await session.execute(select(IngestRun))).scalars().all()
        assert len(list(rows)) == 2
        by_source = {r.source: r for r in rows}
        for name in ("newsapi", "rss"):
            r = by_source[name]
            assert r.items_new == 1
            assert r.items_fetched == 1
            assert r.error is None
            assert r.finished_at is not None


async def test_one_source_failing_doesnt_prevent_others(env):
    factory, store, _ = env

    sources = [
        _FakeSource(name="newsapi", raises=RuntimeError("upstream 500")),
        _FakeSource(
            name="rss",
            items=[_mk_news_item(source="rss", url="https://ok/1", title="ok story")],
        ),
    ]
    orchestrator = IngestOrchestrator(
        session_factory=factory,
        embed=_FakeEmbed(),
        store=store,
        source_factory=lambda _tickers: sources,
    )
    summaries = await orchestrator.run(since=datetime(2026, 7, 3, tzinfo=timezone.utc))

    by_source = {s.source: s for s in summaries}
    assert by_source["newsapi"].error is not None
    assert "upstream 500" in by_source["newsapi"].error
    assert by_source["newsapi"].items_new == 0

    assert by_source["rss"].error is None
    assert by_source["rss"].items_new == 1

    async with factory() as session:
        rows = (await session.execute(select(IngestRun))).scalars().all()
        assert {r.source for r in rows} == {"newsapi", "rss"}


async def test_second_run_dedups_via_persist(env):
    factory, store, _ = env

    def _source_factory(_tickers):
        return [
            _FakeSource(
                name="rss",
                items=[
                    _mk_news_item(source="rss", url="https://a/1", title="Fed hikes"),
                    _mk_news_item(source="rss", url="https://a/2", title="Oil rallies"),
                ],
            )
        ]

    orchestrator = IngestOrchestrator(
        session_factory=factory,
        embed=_FakeEmbed(),
        store=store,
        source_factory=_source_factory,
    )
    since = datetime(2026, 7, 3, tzinfo=timezone.utc)

    first = await orchestrator.run(since=since)
    assert first[0].items_new == 2
    assert first[0].items_deduped == 0

    second = await orchestrator.run(since=since)
    assert second[0].items_new == 0
    assert second[0].items_deduped == 2

    async with factory() as session:
        news = list((await session.execute(select(NewsItem))).scalars().all())
        assert len(news) == 2


async def test_health_ingest_endpoint(env):
    factory, store, _ = env

    def _sf(_):
        return [
            _FakeSource(
                name="newsapi",
                items=[_mk_news_item(source="newsapi", url="https://a/1", title="Fed hikes")],
            ),
            _FakeSource(name="rss", raises=RuntimeError("rss transport error")),
        ]

    orchestrator = IngestOrchestrator(
        session_factory=factory, embed=_FakeEmbed(), store=store, source_factory=_sf
    )
    await orchestrator.run(since=datetime(2026, 7, 3, tzinfo=timezone.utc))

    async def _session_override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db_session] = _session_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/health/ingest")
        assert r.status_code == 200
        body = r.json()["data"]
        by_source = {s["source"]: s for s in body["sources"]}
        assert by_source["newsapi"]["last_status"] == "ok"
        assert by_source["newsapi"]["items_new_last_run"] == 1
        assert by_source["rss"]["last_status"] == "error"
        assert "rss transport error" in by_source["rss"]["error"]
        for s in body["sources"]:
            assert s["last_run_at"] is not None
    finally:
        app.dependency_overrides.clear()
