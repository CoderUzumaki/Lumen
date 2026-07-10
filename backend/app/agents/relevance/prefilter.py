"""Embedding-based relevance prefilter (REL-02).

The prefilter answers "could this cluster plausibly matter to this portfolio?"
in one Chroma lookup + a handful of cosine similarities, so we don't pay LLM
tokens on the ~80% of clusters that are obviously irrelevant.

Flow:
1. Load the portfolio's positions and the owner's themes.
2. Compute the cluster centroid from its item embeddings in Chroma.
3. Embed each position as `f"{ticker} {asset_type} {exchange}"` on the fly.
4. Read each theme's stored vector from the themes Chroma collection.
5. Compute cosine similarities to the cluster centroid.
6. If `max(similarities) < PREFILTER_THRESHOLD` (default 0.35), write a
   `stage='prefilter'` row and short-circuit — the classifier is never invoked.
7. Otherwise, return the shortlist of positions/themes ≥ threshold for the
   classifier stage (REL-03).

If the cluster has no embeddings yet (edge case), the prefilter yields
`passed=True` so the classifier can look at the raw text — the LLM might
still know something the vectors don't.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.news import NewsItem
from app.db.models.portfolio import Portfolio
from app.db.models.position import Position
from app.db.models.relevance import RelevanceScore
from app.db.models.theme import Theme
from app.db.vectorstore import VectorStore
from app.utils.config import Config
from app.utils.embeddings import EmbeddingClient

log = logging.getLogger(__name__)


@dataclass
class PrefilterResult:
    """Prefilter verdict + candidate shortlists for the classifier stage."""

    passed: bool
    max_similarity: float
    candidate_position_ids: list[UUID] = field(default_factory=list)
    candidate_theme_ids: list[UUID] = field(default_factory=list)
    # Populated only when `passed=False`; the row already committed.
    persisted_row: RelevanceScore | None = None


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity. Zero vectors → 0.0 (avoid /0)."""
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        fx = float(x)
        fy = float(y)
        dot += fx * fy
        na += fx * fx
        nb += fy * fy
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _mean_vector(vectors: list[list[float]]) -> list[float] | None:
    if not vectors:
        return None
    dim = len(vectors[0])
    sums = [0.0] * dim
    for v in vectors:
        for i, x in enumerate(v):
            sums[i] += float(x)
    n = float(len(vectors))
    return [s / n for s in sums]


async def run_prefilter(
    *,
    cluster_id: UUID,
    portfolio_id: UUID,
    session: AsyncSession,
    news_store: VectorStore,
    themes_store: VectorStore,
    embed: EmbeddingClient,
    threshold: float | None = None,
) -> PrefilterResult:
    thr = Config.PREFILTER_THRESHOLD if threshold is None else threshold

    portfolio = (
        await session.execute(select(Portfolio).where(Portfolio.id == portfolio_id))
    ).scalar_one_or_none()
    if portfolio is None:
        raise ValueError(f"portfolio {portfolio_id} not found")

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
            await session.execute(
                select(Theme).where(Theme.user_id == portfolio.user_id)
            )
        )
        .scalars()
        .all()
    )

    centroid = await _cluster_centroid(cluster_id, session, news_store)
    if centroid is None:
        # Nothing indexed yet — punt to the classifier rather than emit a
        # low-signal prefilter row.
        return PrefilterResult(passed=True, max_similarity=0.0)

    # Per-position vectors (embedded on the fly per BUILD.md's spec).
    position_texts = [
        f"{p.ticker} {p.asset_type} {p.exchange or ''}".strip() for p in positions
    ]
    position_vecs = await embed.embed(position_texts) if position_texts else []

    # Per-theme vectors: fetch the pre-stored ones from the themes collection.
    theme_vec_by_id: dict[UUID, list[float]] = {}
    if themes:
        got = themes_store.get(
            ids=[str(t.id) for t in themes], include=["embeddings"]
        )
        got_ids = got.get("ids") or []
        got_embs = got.get("embeddings")
        if got_embs is not None:
            for gid, emb in zip(got_ids, got_embs):
                if emb is None or len(emb) == 0:
                    continue
                try:
                    theme_vec_by_id[UUID(gid)] = list(emb)
                except ValueError:
                    continue

    position_sims: dict[UUID, float] = {}
    for p, v in zip(positions, position_vecs):
        position_sims[p.id] = _cosine(centroid, v)

    theme_sims: dict[UUID, float] = {}
    for t in themes:
        v = theme_vec_by_id.get(t.id)
        if v is None:
            continue
        theme_sims[t.id] = _cosine(centroid, v)

    all_sims = list(position_sims.values()) + list(theme_sims.values())
    max_sim = max(all_sims) if all_sims else 0.0

    if max_sim < thr:
        row = RelevanceScore(
            cluster_id=cluster_id,
            user_id=portfolio.user_id,
            portfolio_id=portfolio_id,
            score=Decimal(f"{max(0.0, min(1.0, max_sim)):.2f}"),
            touched_position_ids=[],
            touched_theme_ids=[],
            stage="prefilter",
            rationale=None,
        )
        session.add(row)
        await session.commit()
        return PrefilterResult(
            passed=False,
            max_similarity=max_sim,
            persisted_row=row,
        )

    candidate_positions = [
        p.id for p in positions if position_sims.get(p.id, -1.0) >= thr
    ]
    candidate_themes = [
        t.id for t in themes if theme_sims.get(t.id, -1.0) >= thr
    ]
    return PrefilterResult(
        passed=True,
        max_similarity=max_sim,
        candidate_position_ids=candidate_positions,
        candidate_theme_ids=candidate_themes,
    )


async def _cluster_centroid(
    cluster_id: UUID,
    session: AsyncSession,
    news_store: VectorStore,
) -> list[float] | None:
    item_ids = list(
        (
            await session.execute(
                select(NewsItem.id).where(NewsItem.cluster_id == cluster_id)
            )
        )
        .scalars()
        .all()
    )
    if not item_ids:
        return None
    got = news_store.get(
        ids=[str(i) for i in item_ids], include=["embeddings"]
    )
    raw = got.get("embeddings")
    if raw is None or len(raw) == 0:
        return None
    vecs = [list(v) for v in raw if v is not None and len(v) > 0]
    if not vecs:
        return None
    return _mean_vector(vecs)
