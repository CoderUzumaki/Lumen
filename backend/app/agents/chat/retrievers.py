"""Chat retrieval tools (CHAT-02).

Three async tools the chat agent (CHAT-03) will call as a step in its LangGraph:

- `retrieve_recent_impacts` — the caller's freshest, most-confident impact
  assessments over a lookback window. Skips rows whose impact generation hit
  a guardrail violation (they aren't useful context).
- `retrieve_news` — RAG over the `news_items` Chroma collection, then
  filtered to items whose cluster touches at least one of the caller's
  tickers. Snippets are truncated to 500 chars.
- `get_portfolio_summary` — one-shot snapshot: positions, themes, and the
  most-recent briefing's `generated_summary`. Returns `None` if the
  portfolio isn't the caller's (defensive cross-user check).

All three are non-LLM. Every DB query is scoped by `user_id` for isolation.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.briefing import Briefing
from app.db.models.impact import ImpactAssessment
from app.db.models.news import NewsCluster, NewsItem
from app.db.models.portfolio import Portfolio
from app.db.models.position import Position
from app.db.models.theme import Theme
from app.db.vectorstore import VectorStore
from app.schemas.impact import ImpactRead
from app.utils.embeddings import EmbeddingClient

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Return schemas
# ---------------------------------------------------------------------------


class ChatNewsSnippet(BaseModel):
    """Compact news snippet — enough to ground a claim, not a full body."""

    model_config = ConfigDict(from_attributes=True)

    item_id: UUID
    cluster_id: UUID | None
    title: str
    url: str
    source: str
    published_at: datetime
    snippet: str  # body[:500] or title if body absent
    similarity: float = Field(ge=0.0, le=1.0)


class PortfolioSummary(BaseModel):
    """Snapshot of the caller's active portfolio for the chat agent's prompt."""

    portfolio_id: UUID
    portfolio_name: str
    positions: list[dict[str, Any]]
    themes: list[dict[str, Any]]
    latest_briefing_summary: str | None = None
    latest_briefing_date: date | None = None


# ---------------------------------------------------------------------------
# Tool 1 — recent impacts
# ---------------------------------------------------------------------------


async def retrieve_recent_impacts(
    user_id: UUID,
    portfolio_id: UUID,
    *,
    session: AsyncSession,
    lookback_days: int = 7,
    k: int = 5,
) -> list[ImpactRead]:
    """Top-k confidence-ranked impact assessments in the last `lookback_days`.

    Skips rows with non-empty `guardrail_violations` (those represent failed
    impact generations and aren't useful chat context). Cross-user isolated
    via the WHERE clause.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    stmt = (
        select(ImpactAssessment)
        .where(
            ImpactAssessment.user_id == user_id,
            ImpactAssessment.portfolio_id == portfolio_id,
            ImpactAssessment.created_at >= cutoff,
        )
        .order_by(
            ImpactAssessment.confidence.desc(),
            ImpactAssessment.created_at.desc(),
        )
        # Over-fetch: some rows will get filtered by the guardrail check
        # below (typically ~0). k*3 is a cheap upper bound.
        .limit(max(k * 3, k + 5))
    )
    rows = list((await session.execute(stmt)).scalars().all())

    kept: list[ImpactRead] = []
    skipped = 0
    for row in rows:
        gv = row.guardrail_violations or []
        if len(gv) > 0:
            skipped += 1
            continue
        kept.append(ImpactRead.model_validate(row))
        if len(kept) >= k:
            break

    if skipped:
        log.debug(
            "retrieve_recent_impacts: skipped %d row(s) with guardrail violations",
            skipped,
        )
    return kept


# ---------------------------------------------------------------------------
# Tool 2 — news RAG scoped to the caller's tickers
# ---------------------------------------------------------------------------


async def _user_tickers(
    session: AsyncSession, portfolio_id: UUID
) -> set[str]:
    rows = (
        await session.execute(
            select(Position.ticker).where(Position.portfolio_id == portfolio_id)
        )
    ).scalars().all()
    return {t for t in rows if t}


def _cluster_touches(cluster: NewsCluster | None, tickers: set[str]) -> bool:
    """True if the cluster's `entity_tickers` intersect the user's set."""
    if cluster is None:
        return False
    if not cluster.entity_tickers:
        return False
    return any(t in tickers for t in cluster.entity_tickers)


async def retrieve_news(
    query: str,
    user_id: UUID,  # noqa: ARG001 — reserved for future audit / rate-limiting
    portfolio_id: UUID,
    *,
    session: AsyncSession,
    news_store: VectorStore,
    embed: EmbeddingClient,
    k: int = 5,
    since_days: int = 30,
    min_similarity: float = 0.35,
) -> list[ChatNewsSnippet]:
    """Semantic search over `news_items`, filtered to items touching the caller's tickers."""
    query_clean = query.strip()
    if not query_clean:
        return []

    tickers = await _user_tickers(session, portfolio_id)
    if not tickers:
        return []

    query_vec = await embed.embed([query_clean])
    if not query_vec:
        return []

    # Over-fetch: filtering by ticker + similarity may drop most hits.
    result = news_store.query(
        query_embeddings=query_vec, n_results=max(k * 4, k + 10)
    )
    ids_list: list[str] = (result.get("ids") or [[]])[0]
    distances: list[float] = (result.get("distances") or [[]])[0]

    if not ids_list:
        return []

    # Bulk-fetch the NewsItem rows + their clusters.
    item_uuids: list[UUID] = []
    for raw in ids_list:
        try:
            item_uuids.append(UUID(raw))
        except (TypeError, ValueError):
            continue
    if not item_uuids:
        return []

    items = list(
        (
            await session.execute(
                select(NewsItem).where(NewsItem.id.in_(item_uuids))
            )
        )
        .scalars()
        .all()
    )
    by_id = {i.id: i for i in items}

    cluster_ids = {i.cluster_id for i in items if i.cluster_id}
    clusters_by_id: dict[UUID, NewsCluster] = {}
    if cluster_ids:
        clusters_by_id = {
            c.id: c
            for c in (
                await session.execute(
                    select(NewsCluster).where(NewsCluster.id.in_(cluster_ids))
                )
            )
            .scalars()
            .all()
        }

    since_cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)

    snippets: list[ChatNewsSnippet] = []
    for raw_id, dist in zip(ids_list, distances):
        try:
            uid = UUID(raw_id)
        except (TypeError, ValueError):
            continue
        item = by_id.get(uid)
        if item is None:
            continue

        # Cross-DB freshness gate. sqlite drops tzinfo on round-trip, so coerce.
        published = item.published_at
        if published is not None and published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if published is None or published < since_cutoff:
            continue

        cluster = clusters_by_id.get(item.cluster_id) if item.cluster_id else None
        if not _cluster_touches(cluster, tickers):
            continue

        try:
            similarity = 1.0 - float(dist)
        except (TypeError, ValueError):
            continue
        similarity = max(0.0, min(1.0, similarity))
        if similarity < min_similarity:
            continue

        body = item.body or ""
        snippet_text = (body if body else item.title)[:500]

        snippets.append(
            ChatNewsSnippet(
                item_id=item.id,
                cluster_id=item.cluster_id,
                title=item.title,
                url=item.url,
                source=item.source,
                published_at=item.published_at,
                snippet=snippet_text,
                similarity=similarity,
            )
        )

    snippets.sort(key=lambda s: s.similarity, reverse=True)
    return snippets[:k]


# ---------------------------------------------------------------------------
# Tool 3 — portfolio summary
# ---------------------------------------------------------------------------


async def get_portfolio_summary(
    user_id: UUID,
    portfolio_id: UUID,
    *,
    session: AsyncSession,
) -> PortfolioSummary | None:
    """Snapshot of the caller's active portfolio + latest briefing summary.

    Returns None if the portfolio isn't the caller's — defensive isolation
    even if the caller passes a stolen `portfolio_id`.
    """
    portfolio = (
        await session.execute(
            select(Portfolio).where(
                Portfolio.id == portfolio_id, Portfolio.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if portfolio is None:
        return None

    positions = list(
        (
            await session.execute(
                select(Position).where(Position.portfolio_id == portfolio_id)
            )
        )
        .scalars()
        .all()
    )
    themes = list(
        (
            await session.execute(select(Theme).where(Theme.user_id == user_id))
        )
        .scalars()
        .all()
    )

    latest_briefing = (
        await session.execute(
            select(Briefing)
            .where(
                Briefing.user_id == user_id,
                Briefing.portfolio_id == portfolio_id,
            )
            .order_by(Briefing.briefing_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    latest_summary: str | None = None
    latest_date: date | None = None
    if latest_briefing is not None:
        latest_date = latest_briefing.briefing_date
        content = latest_briefing.structured_content or {}
        if isinstance(content, dict):
            gs = content.get("generated_summary")
            if isinstance(gs, str) and gs:
                latest_summary = gs

    return PortfolioSummary(
        portfolio_id=portfolio.id,
        portfolio_name=portfolio.name,
        positions=[
            {
                "ticker": p.ticker,
                "asset_type": p.asset_type,
                "quantity": str(p.quantity) if p.quantity is not None else None,
                "currency": p.currency,
            }
            for p in positions
        ],
        themes=[
            {"description": t.description, "weight": str(t.weight)}
            for t in themes
        ],
        latest_briefing_summary=latest_summary,
        latest_briefing_date=latest_date,
    )
