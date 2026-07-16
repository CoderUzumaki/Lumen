"""Fan-out worker: score every new/updated cluster for every active portfolio (REL-05).

After each ingest cycle (ING-10) the orchestrator hands this module either a
concrete list of cluster ids or a `since` timestamp. For each cluster and each
active portfolio, we enqueue `score_cluster_for_user()` under an
`asyncio.Semaphore(concurrency)` (default 10). Each task uses its own
AsyncSession — SQLAlchemy async sessions aren't concurrency-safe.

Idempotency is inherited from `score_cluster_for_user()` — the underlying
graph checks the unique `(cluster, user, portfolio)` key and short-circuits on
a cache hit, so re-running the fan-out over the same window produces zero new
rows.

Per-cluster cost estimates are emitted as structured log lines. Fast-tier
classifier calls are the only LLM cost here; the prefilter is embedding-only.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.relevance.graph import score_cluster_for_user
from app.db.models import NewsCluster, Portfolio, RelevanceScore
from app.db.vectorstore import VectorStore
from app.utils.embeddings import EmbeddingClient
from app.utils.llm import LLMClient

log = logging.getLogger(__name__)


# Rough token count for the classifier prompt+completion. Fast-tier free-tier
# on OpenRouter has $0 marginal cost; this is an operational counter, not a
# billing signal. See PRD §11.4.
_CLASSIFIER_EST_TOKENS = 800


@dataclass
class FanoutSummary:
    """Aggregate counts for one fan-out invocation."""

    tasks: int = 0
    cache_hits: int = 0
    prefilter_short_circuits: int = 0
    classifier_calls: int = 0
    errors: int = 0
    elapsed_seconds: float = 0.0
    cluster_ids: list[UUID] = field(default_factory=list)


async def _discover_cluster_ids(
    session: AsyncSession, since: datetime
) -> list[UUID]:
    """Clusters created or updated at/after `since`."""
    rows = (
        await session.execute(
            select(NewsCluster.id).where(NewsCluster.last_seen_at >= since)
        )
    ).scalars().all()
    return list(rows)


async def _active_portfolios(session: AsyncSession) -> list[tuple[UUID, UUID]]:
    """Return [(user_id, portfolio_id)] for every active portfolio."""
    rows = (
        await session.execute(
            select(Portfolio.user_id, Portfolio.id).where(Portfolio.is_active.is_(True))
        )
    ).all()
    return [(u, p) for (u, p) in rows]


@dataclass
class _TaskOutcome:
    """One (cluster, portfolio) task result — used for per-cluster aggregation."""

    stage: str | None = None  # 'prefilter' | 'classifier' | None on error
    was_cached: bool = False
    error: str | None = None


async def _score_one(
    *,
    cluster_id: UUID,
    user_id: UUID,
    portfolio_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
    news_store: VectorStore,
    themes_store: VectorStore,
    embed: EmbeddingClient,
    llm: LLMClient,
    semaphore: asyncio.Semaphore,
) -> _TaskOutcome:
    async with semaphore:
        try:
            async with session_factory() as session:
                # Cheap probe: was a row already present *before* we invoked
                # the graph? If so, this task is a cache hit and no LLM/embed
                # work happened. We check first so the outcome can be tallied
                # cleanly (score_cluster_for_user returns the same row shape
                # either way).
                existed = (
                    await session.execute(
                        select(RelevanceScore.id).where(
                            RelevanceScore.cluster_id == cluster_id,
                            RelevanceScore.user_id == user_id,
                            RelevanceScore.portfolio_id == portfolio_id,
                        )
                    )
                ).scalar_one_or_none()

                row = await score_cluster_for_user(
                    cluster_id,
                    user_id,
                    portfolio_id,
                    session=session,
                    news_store=news_store,
                    themes_store=themes_store,
                    embed=embed,
                    llm=llm,
                )
                return _TaskOutcome(stage=row.stage, was_cached=existed is not None)
        except Exception as exc:  # noqa: BLE001
            log.exception(
                "fanout: score failed cluster=%s portfolio=%s", cluster_id, portfolio_id
            )
            return _TaskOutcome(error=str(exc)[:200])


async def run_fanout(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    news_store: VectorStore,
    themes_store: VectorStore,
    embed: EmbeddingClient,
    llm: LLMClient,
    cluster_ids: Iterable[UUID] | None = None,
    since: datetime | None = None,
    concurrency: int = 10,
) -> FanoutSummary:
    """Score every cluster in the target set × every active portfolio.

    Exactly one of `cluster_ids` or `since` must be provided.

    Returns a `FanoutSummary` with per-outcome counts and the wall-clock
    elapsed. Per-cluster cost estimates are emitted as structured log lines.
    """
    if cluster_ids is None and since is None:
        raise ValueError("run_fanout requires either cluster_ids or since")

    started = time.monotonic()

    async with session_factory() as session:
        if cluster_ids is not None:
            clusters = list(cluster_ids)
        else:
            assert since is not None
            clusters = await _discover_cluster_ids(session, since)
        portfolios = await _active_portfolios(session)

    summary = FanoutSummary(cluster_ids=clusters)

    if not clusters or not portfolios:
        summary.elapsed_seconds = time.monotonic() - started
        log.info(
            "fanout: nothing to do clusters=%d portfolios=%d",
            len(clusters),
            len(portfolios),
        )
        return summary

    semaphore = asyncio.Semaphore(max(1, concurrency))

    # Group by cluster so we can emit a per-cluster cost log line as each
    # cluster's set of portfolio tasks completes.
    for cluster_id in clusters:
        outcomes = await asyncio.gather(
            *(
                _score_one(
                    cluster_id=cluster_id,
                    user_id=user_id,
                    portfolio_id=portfolio_id,
                    session_factory=session_factory,
                    news_store=news_store,
                    themes_store=themes_store,
                    embed=embed,
                    llm=llm,
                    semaphore=semaphore,
                )
                for (user_id, portfolio_id) in portfolios
            )
        )
        cache_hits = sum(1 for o in outcomes if o.was_cached)
        prefilter_hits = sum(
            1 for o in outcomes if not o.was_cached and o.stage == "prefilter"
        )
        classifier_hits = sum(
            1 for o in outcomes if not o.was_cached and o.stage == "classifier"
        )
        errors = sum(1 for o in outcomes if o.error is not None)

        summary.tasks += len(outcomes)
        summary.cache_hits += cache_hits
        summary.prefilter_short_circuits += prefilter_hits
        summary.classifier_calls += classifier_hits
        summary.errors += errors

        log.info(
            "fanout_cluster cluster=%s portfolios=%d cache=%d prefilter=%d "
            "classifier=%d errors=%d est_tokens=%d",
            cluster_id,
            len(outcomes),
            cache_hits,
            prefilter_hits,
            classifier_hits,
            errors,
            classifier_hits * _CLASSIFIER_EST_TOKENS,
        )

    summary.elapsed_seconds = time.monotonic() - started
    log.info(
        "fanout_done clusters=%d portfolios=%d tasks=%d cache=%d prefilter=%d "
        "classifier=%d errors=%d elapsed=%.2fs",
        len(clusters),
        len(portfolios),
        summary.tasks,
        summary.cache_hits,
        summary.prefilter_short_circuits,
        summary.classifier_calls,
        summary.errors,
        summary.elapsed_seconds,
    )
    return summary
