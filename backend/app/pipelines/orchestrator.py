"""Ingestion orchestrator + APScheduler wiring (ING-10).

`IngestOrchestrator.run()` executes one pass of the pipeline across every
source. For each source:
  1. Opens an `ingest_runs` row (`started_at = now`).
  2. `fetch(since)` → `normalize()` → `persist()` → `cluster_item()`.
  3. Closes the row with `finished_at`, item counts, or an error message.

Errors are caught **per source** — one adapter blowing up (5xx, transport
error, bad payload) never prevents the others from running.

The scheduler-facing entrypoint is `IngestOrchestrator.run()`. `main.py`
constructs a process-global orchestrator + APScheduler at startup and
schedules a run every `Config.INGEST_INTERVAL_MINUTES` (default 15), with
the first invocation delayed 30s past boot so uvicorn's healthcheck window
doesn't collide with expensive first-time work.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import IngestRun, NewsItem, Position
from app.db.vectorstore import VectorStore
from app.pipelines.clusterer import cluster_item
from app.pipelines.normalizer import normalize
from app.pipelines.persist import persist
from app.pipelines.sources.base import BaseSource
from app.utils.config import Config
from app.utils.embeddings import EmbeddingClient

log = logging.getLogger(__name__)


SourceFactory = Callable[[list[str]], list[BaseSource]]


@dataclass
class IngestRunSummary:
    """Per-source outcome for one orchestrator pass."""

    source: str
    started_at: datetime
    finished_at: datetime | None
    items_fetched: int
    items_new: int
    items_deduped: int
    error: str | None


async def _load_known_tickers(session: AsyncSession) -> list[str]:
    """Union of every ticker across all user positions."""
    q = select(distinct(Position.ticker))
    result = await session.execute(q)
    return sorted(str(t) for t in result.scalars().all())


class IngestOrchestrator:
    """One instance per process; drives the ingest → cluster pipeline."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        embed: EmbeddingClient,
        store: VectorStore,
        source_factory: SourceFactory,
        lookback: timedelta | None = None,
    ):
        self._session_factory = session_factory
        self._embed = embed
        self._store = store
        self._source_factory = source_factory
        # By default pull twice the ingest interval — small overlap tolerates
        # slow adapters and gives idempotent persist headroom to dedupe.
        self._lookback = lookback or timedelta(
            minutes=Config.INGEST_INTERVAL_MINUTES * 2
        )

    async def run(self, since: datetime | None = None) -> list[IngestRunSummary]:
        """Execute one ingest pass across every source. Returns per-source summary."""
        now = datetime.now(timezone.utc)
        effective_since = (since or (now - self._lookback)).astimezone(timezone.utc)

        # Union tickers now so every source sees the same set.
        async with self._session_factory() as session:
            known_tickers = await _load_known_tickers(session)
        known_set = set(known_tickers)

        sources = self._source_factory(known_tickers)
        summaries: list[IngestRunSummary] = []

        for src in sources:
            summary = await self._run_one_source(
                src, since=effective_since, known_tickers=known_set
            )
            summaries.append(summary)

        return summaries

    async def _run_one_source(
        self,
        source: BaseSource,
        *,
        since: datetime,
        known_tickers: set[str],
    ) -> IngestRunSummary:
        started = datetime.now(timezone.utc)
        source_name = getattr(source, "source_name", type(source).__name__)

        # Open the ingest_runs row.
        run_id: UUID | None = None
        try:
            async with self._session_factory() as session:
                run_row = IngestRun(source=source_name, started_at=started)
                session.add(run_row)
                await session.commit()
                await session.refresh(run_row)
                run_id = run_row.id
        except Exception:
            log.exception("orchestrator: could not open ingest_runs row for %s", source_name)

        items_fetched = 0
        items_new = 0
        items_deduped = 0
        error: str | None = None

        try:
            fetched = await source.fetch(since)
            items_fetched = len(fetched)
            if fetched:
                normalized = [normalize(i, known_tickers=known_tickers) for i in fetched]
                tickers_by_hash = {n.url_hash: n.tickers for n in normalized}
                async with self._session_factory() as session:
                    items_new, items_deduped = await persist(
                        normalized,
                        session=session,
                        embed=self._embed,
                        store=self._store,
                    )
                    inserted_rows: list[NewsItem] = []
                    if items_new > 0:
                        inserted_rows = list(
                            (
                                await session.execute(
                                    select(NewsItem).where(
                                        NewsItem.url_hash.in_(
                                            list(tickers_by_hash.keys())
                                        ),
                                        NewsItem.cluster_id.is_(None),
                                    )
                                )
                            )
                            .scalars()
                            .all()
                        )
                    for row in inserted_rows:
                        try:
                            await cluster_item(
                                row,
                                session=session,
                                store=self._store,
                                tickers=tickers_by_hash.get(row.url_hash, []),
                            )
                        except Exception:
                            log.exception(
                                "orchestrator: clustering failed for %s (%s)",
                                row.id,
                                source_name,
                            )
        except Exception as e:
            log.exception("orchestrator: source %s failed", source_name)
            error = str(e)[:500]

        finished = datetime.now(timezone.utc)

        # Close the row.
        if run_id is not None:
            try:
                async with self._session_factory() as session:
                    row = (
                        await session.execute(
                            select(IngestRun).where(IngestRun.id == run_id)
                        )
                    ).scalar_one()
                    row.finished_at = finished
                    row.items_fetched = items_fetched
                    row.items_new = items_new
                    row.items_deduped = items_deduped
                    row.error = error
                    await session.commit()
            except Exception:
                log.exception(
                    "orchestrator: could not close ingest_runs row for %s", source_name
                )

        # Try to close per-source resources (adapters with an http_client they own).
        aclose = getattr(source, "aclose", None)
        if aclose is not None:
            try:
                await aclose()
            except Exception:
                log.exception("orchestrator: aclose() failed for %s", source_name)

        return IngestRunSummary(
            source=source_name,
            started_at=started,
            finished_at=finished,
            items_fetched=items_fetched,
            items_new=items_new,
            items_deduped=items_deduped,
            error=error,
        )


async def latest_per_source(session: AsyncSession) -> list[IngestRun]:
    """Latest `ingest_runs` row per source, most recent first."""
    from sqlalchemy import func

    # Postgres and sqlite both support DISTINCT ON via window function or
    # subquery. Use a portable subquery: for each source, take MAX(started_at).
    latest = (
        select(IngestRun.source, func.max(IngestRun.started_at).label("mx"))
        .group_by(IngestRun.source)
        .subquery()
    )
    q = (
        select(IngestRun)
        .join(
            latest,
            (IngestRun.source == latest.c.source)
            & (IngestRun.started_at == latest.c.mx),
        )
        .order_by(IngestRun.source)
    )
    result = await session.execute(q)
    return list(result.scalars().all())


def default_source_factory(known_tickers: list[str]) -> list[BaseSource]:
    """Build the production five-source list. `main.py` uses this at startup."""
    from app.pipelines.sources.edgar import EDGARSource
    from app.pipelines.sources.gdelt import GDELTSource
    from app.pipelines.sources.marketaux import MarketauxSource
    from app.pipelines.sources.newsapi import NewsAPISource
    from app.pipelines.sources.rss import RSSSource

    sources: list[BaseSource] = [
        NewsAPISource(),
        MarketauxSource(),
        RSSSource(),
    ]
    if Config.GDELT_ENABLED:
        sources.append(GDELTSource())
    if known_tickers:
        sources.append(EDGARSource(tickers=known_tickers))
    return sources


def _to_health_payload(rows: list[IngestRun]) -> list[dict[str, Any]]:
    return [
        {
            "source": r.source,
            "last_run_at": r.started_at.isoformat() if r.started_at else None,
            "last_status": (
                "error"
                if r.error
                else ("running" if r.finished_at is None else "ok")
            ),
            "items_new_last_run": r.items_new,
            "error": r.error,
        }
        for r in rows
    ]
