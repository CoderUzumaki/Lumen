"""LLM classifier for the relevance graph (REL-03).

Given the cluster + a prefilter shortlist, ask the fast-tier LLM to pick
which of the candidate positions/themes are materially affected and emit a
score with a one-sentence mechanism. Structured output is enforced via
Pydantic (`RelevanceVerdict`) so parse-or-retry lives inside the LLM wrapper
(see BOOT-06).

Persistence: a `stage='classifier'` `relevance_scores` row keyed on
(cluster, user, portfolio). Downstream (REL-04) enforces idempotency; this
module always writes.

Guardrail: the classifier's output UUIDs are intersected with the input
shortlist before persisting, so a hallucinated id can't sneak into the DB.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.news import NewsCluster, NewsItem
from app.db.models.portfolio import Portfolio
from app.db.models.position import Position
from app.db.models.relevance import RelevanceScore
from app.db.models.theme import Theme
from app.utils.llm import LLMClient, Message

log = logging.getLogger(__name__)


_BODY_MAX_CHARS = 1500


class RelevanceVerdict(BaseModel):
    """Structured output of the classifier LLM call."""

    score: float = Field(..., ge=0.0, le=1.0)
    touched_positions: list[UUID] = Field(default_factory=list)
    touched_themes: list[UUID] = Field(default_factory=list)
    rationale: str = Field(..., max_length=500)


_SYSTEM_PROMPT = (
    "You are Lumen's relevance classifier. Given a news event and a shortlist "
    "of candidate portfolio positions and macro themes, decide which of them "
    "are *materially* affected by the event. Return a JSON object with keys "
    "`score` (float 0-1), `touched_positions` (list of position UUIDs from the "
    "shortlist), `touched_themes` (list of theme UUIDs from the shortlist), "
    "and `rationale` (a single sentence naming the transmission mechanism). "
    "Use mechanism language — never recommend buy, sell, or hold."
)


def _build_user_prompt(
    cluster: NewsCluster,
    body: str | None,
    positions: list[Position],
    themes: list[Theme],
) -> str:
    parts: list[str] = [f"Event: {cluster.canonical_title}"]
    if body:
        parts.append(f"Body: {body[:_BODY_MAX_CHARS]}")
    if positions:
        parts.append("Candidate positions:")
        for p in positions:
            parts.append(
                f"- id={p.id} ticker={p.ticker} asset_type={p.asset_type}"
                + (f" exchange={p.exchange}" if p.exchange else "")
            )
    if themes:
        parts.append("Candidate themes:")
        for t in themes:
            parts.append(f'- id={t.id} description="{t.description}"')
    return "\n".join(parts)


async def run_classifier(
    *,
    cluster_id: UUID,
    portfolio_id: UUID,
    candidate_position_ids: Iterable[UUID],
    candidate_theme_ids: Iterable[UUID],
    session: AsyncSession,
    llm: LLMClient,
    agent_name: str = "relevance-classifier",
) -> RelevanceScore:
    cluster = (
        await session.execute(select(NewsCluster).where(NewsCluster.id == cluster_id))
    ).scalar_one()
    portfolio = (
        await session.execute(select(Portfolio).where(Portfolio.id == portfolio_id))
    ).scalar_one()

    latest_body = (
        await session.execute(
            select(NewsItem)
            .where(NewsItem.cluster_id == cluster_id)
            .order_by(NewsItem.published_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    body = latest_body.body if latest_body else None

    pos_ids = list(candidate_position_ids)
    positions: list[Position] = []
    if pos_ids:
        positions = list(
            (
                await session.execute(
                    select(Position).where(Position.id.in_(pos_ids))
                )
            )
            .scalars()
            .all()
        )

    theme_ids = list(candidate_theme_ids)
    themes: list[Theme] = []
    if theme_ids:
        themes = list(
            (
                await session.execute(
                    select(Theme).where(Theme.id.in_(theme_ids))
                )
            )
            .scalars()
            .all()
        )

    messages = [
        Message(role="system", content=_SYSTEM_PROMPT),
        Message(
            role="user",
            content=_build_user_prompt(cluster, body, positions, themes),
        ),
    ]

    response = await llm.complete(
        messages,
        tier="fast",
        response_model=RelevanceVerdict,
        user_id=portfolio.user_id,
        agent_name=agent_name,
    )
    verdict: RelevanceVerdict = response.parsed  # type: ignore[assignment]

    # Guardrail: constrain touched_* to the input shortlist.
    valid_pos = {p.id for p in positions}
    valid_theme = {t.id for t in themes}
    touched_positions = [p for p in verdict.touched_positions if p in valid_pos]
    touched_themes = [t for t in verdict.touched_themes if t in valid_theme]

    row = RelevanceScore(
        cluster_id=cluster_id,
        user_id=portfolio.user_id,
        portfolio_id=portfolio_id,
        score=Decimal(f"{max(0.0, min(1.0, verdict.score)):.2f}"),
        touched_position_ids=[str(p) for p in touched_positions],
        touched_theme_ids=[str(t) for t in touched_themes],
        stage="classifier",
        rationale=verdict.rationale,
    )
    session.add(row)
    await session.commit()
    return row
