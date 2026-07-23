"""News read endpoints (REL-06).

Two endpoints, both authed via `require_auth`:

- `GET /api/news/relevant?limit=&since=` — the caller's active portfolio's
  scored feed, ordered by `relevance.score DESC, cluster.last_seen_at DESC`.
- `GET /api/news/clusters/{cluster_id}` — a single cluster with its items,
  the caller's own relevance row (if any), and a placeholder `impact` slot
  reserved for IMP-01.

Cross-user isolation: every query filters `relevance_scores.user_id ==
caller.user_id`. There is no path where a user can observe another user's
relevance rows. Clusters themselves are ingested globally and are visible to
any authenticated caller — this matches the news-corpus model in the PRD.

Ordering: BUILD.md specifies `score DESC, published_at DESC`. The cluster
carries `last_seen_at` (bumped when the newest item dedupes in) as the
natural cluster-freshness proxy; we sort on it rather than joining the items
table just to order, which would spend an index scan for no user-visible gain.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db_session
from app.db.models.impact import ImpactAssessment
from app.db.models.news import NewsCluster, NewsItem
from app.db.models.portfolio import Portfolio
from app.db.models.relevance import RelevanceScore
from app.schemas.impact import ImpactRead
from app.schemas.news import (
    ClusterDetailRead,
    NewsClusterRead,
    NewsItemRead,
    RelevanceRead,
    RelevantClusterRead,
)
from app.utils.auth import UserContext, require_auth

router = APIRouter(prefix="/api/news", tags=["news"])


async def _active_portfolio(user_id: UUID, db: AsyncSession) -> Portfolio | None:
    q = select(Portfolio).where(
        Portfolio.user_id == user_id, Portfolio.is_active.is_(True)
    )
    return (await db.execute(q)).scalar_one_or_none()


def _to_cluster_read(cluster: NewsCluster, items: list[NewsItem]) -> NewsClusterRead:
    read = NewsClusterRead.model_validate(cluster)
    read.items = [NewsItemRead.model_validate(i) for i in items]
    return read


@router.get("/relevant", response_model=list[RelevantClusterRead])
async def relevant_feed(
    limit: int = Query(default=20, ge=1, le=100),
    since: datetime | None = Query(default=None),
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> list[RelevantClusterRead]:
    portfolio = await _active_portfolio(user.user_id, db)
    if portfolio is None:
        # Onboarding-legal state: return empty list rather than 404.
        return []

    stmt = (
        select(RelevanceScore, NewsCluster)
        .join(NewsCluster, NewsCluster.id == RelevanceScore.cluster_id)
        .where(
            RelevanceScore.user_id == user.user_id,
            RelevanceScore.portfolio_id == portfolio.id,
        )
        .order_by(
            RelevanceScore.score.desc(),
            NewsCluster.last_seen_at.desc(),
        )
        .limit(limit)
    )
    if since is not None:
        stmt = stmt.where(NewsCluster.last_seen_at >= since)

    rows = (await db.execute(stmt)).all()
    # Feed keeps clusters lean — no items embedded. The detail endpoint loads
    # them on demand.
    return [
        RelevantClusterRead(
            cluster=NewsClusterRead.model_validate(cluster),
            relevance=RelevanceRead.model_validate(rel),
        )
        for (rel, cluster) in rows
    ]


@router.get("/clusters/{cluster_id}", response_model=ClusterDetailRead)
async def cluster_detail(
    cluster_id: UUID,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> ClusterDetailRead:
    cluster = (
        await db.execute(select(NewsCluster).where(NewsCluster.id == cluster_id))
    ).scalar_one_or_none()
    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="cluster not found"
        )

    items = list(
        (
            await db.execute(
                select(NewsItem)
                .where(NewsItem.cluster_id == cluster_id)
                .order_by(NewsItem.published_at.desc())
            )
        )
        .scalars()
        .all()
    )

    relevance: RelevanceScore | None = None
    impact_row: ImpactAssessment | None = None
    portfolio = await _active_portfolio(user.user_id, db)
    if portfolio is not None:
        relevance = (
            await db.execute(
                select(RelevanceScore).where(
                    RelevanceScore.cluster_id == cluster_id,
                    RelevanceScore.user_id == user.user_id,
                    RelevanceScore.portfolio_id == portfolio.id,
                )
            )
        ).scalar_one_or_none()
        impact_row = (
            await db.execute(
                select(ImpactAssessment).where(
                    ImpactAssessment.cluster_id == cluster_id,
                    ImpactAssessment.user_id == user.user_id,
                    ImpactAssessment.portfolio_id == portfolio.id,
                )
            )
        ).scalar_one_or_none()

    return ClusterDetailRead(
        cluster=_to_cluster_read(cluster, items),
        relevance=RelevanceRead.model_validate(relevance) if relevance else None,
        impact=ImpactRead.model_validate(impact_row) if impact_row else None,
    )
