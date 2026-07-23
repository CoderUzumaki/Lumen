"""Impact endpoints + on-demand generation (IMP-05).

Two endpoints, both authed via `require_auth`:

- `GET /api/news/clusters/{cluster_id}/impact` — returns the caller's cached
  impact for the caller's active portfolio (200), or if none exists and the
  cluster's relevance score for the caller is ≥ `Config.IMPACT_MIN_SCORE`
  (default 0.3), enqueues a background generation and returns 202. Below-
  threshold or absent-relevance clusters return 404.

- `POST /api/news/clusters/{cluster_id}/impact/generate` — same threshold gate;
  always enqueues with `force=True` so the analyst re-runs even when a
  cached row already exists.

Enqueue is a fire-and-forget `asyncio.create_task` whose coroutine opens its
own `AsyncSession`, constructs its own `LLMClient` / `EmbeddingClient` /
`VectorStore("historical_analogs")` (the request-scoped session dies with the
response), and calls `analyze_impact_for_user()`. The IMP-04 idempotency
guarantee — unique on `(cluster_id, user_id, portfolio_id)` — means duplicate
enqueues on the GET path are safe: whichever runs first persists; the loser
returns the cached row on re-invocation.

Cross-user isolation mirrors REL-06: every query filters
`impact_assessments.user_id == caller.user_id`; a user never observes another
user's impact row even for the same cluster.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Callable, Coroutine, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db_session, get_session_factory
from app.db.models.impact import ImpactAssessment
from app.db.models.news import NewsCluster
from app.db.models.portfolio import Portfolio
from app.db.models.relevance import RelevanceScore
from app.db.vectorstore import VectorStore
from app.schemas.impact import ImpactRead
from app.utils.auth import UserContext, require_auth
from app.utils.config import Config
from app.utils.embeddings import EmbeddingClient
from app.utils.llm import LLMClient

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/news/clusters", tags=["impact"])


# Minimum relevance score to allow generation. Below this the endpoint 404s
# — the analyst is expensive and a low-relevance cluster isn't worth the LLM
# spend. `Config.IMPACT_MIN_SCORE` overrides if present; otherwise 0.3 per
# BUILD.md IMP-05.
_IMPACT_MIN_SCORE = Decimal(str(getattr(Config, "IMPACT_MIN_SCORE", 0.3)))


# Type alias for the enqueue callable. Tests override this via
# `app.dependency_overrides[get_impact_enqueue]` so a fake enqueue can run
# synchronously or record calls without touching the real graph.
EnqueueFn = Callable[[UUID, UUID, UUID, bool], Coroutine[Any, Any, None]]


async def _default_enqueue(
    cluster_id: UUID, user_id: UUID, portfolio_id: UUID, force: bool
) -> None:
    """Fire-and-forget background generation. Never raises to the caller."""
    from app.agents.impact.graph import analyze_impact_for_user

    session_factory = get_session_factory()
    embed = EmbeddingClient()
    analogs_store = VectorStore("historical_analogs")
    llm = LLMClient()

    async def _run() -> None:
        try:
            async with session_factory() as session:
                await analyze_impact_for_user(
                    cluster_id,
                    user_id,
                    portfolio_id,
                    session=session,
                    analogs_store=analogs_store,
                    embed=embed,
                    llm=llm,
                    force=force,
                )
        except Exception:  # noqa: BLE001 — background task must never leak
            log.exception(
                "impact generation failed cluster=%s portfolio=%s",
                cluster_id,
                portfolio_id,
            )

    asyncio.create_task(_run())


def get_impact_enqueue() -> EnqueueFn:
    """FastAPI dependency — swap via `app.dependency_overrides` in tests."""
    return _default_enqueue


async def _active_portfolio(user_id: UUID, db: AsyncSession) -> Portfolio | None:
    q = select(Portfolio).where(
        Portfolio.user_id == user_id, Portfolio.is_active.is_(True)
    )
    return (await db.execute(q)).scalar_one_or_none()


async def _load_relevance_score(
    db: AsyncSession, cluster_id: UUID, user_id: UUID, portfolio_id: UUID
) -> Decimal | None:
    row = (
        await db.execute(
            select(RelevanceScore.score).where(
                RelevanceScore.cluster_id == cluster_id,
                RelevanceScore.user_id == user_id,
                RelevanceScore.portfolio_id == portfolio_id,
            )
        )
    ).scalar_one_or_none()
    return row


def _poll_url(request: Request, cluster_id: UUID) -> str:
    """Absolute URL a client can poll to observe generation completion."""
    return str(request.url_for("get_impact", cluster_id=cluster_id))


@router.get("/{cluster_id}/impact", name="get_impact")
async def get_impact(
    cluster_id: UUID,
    request: Request,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
    enqueue: EnqueueFn = Depends(get_impact_enqueue),
):
    portfolio = await _active_portfolio(user.user_id, db)
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active portfolio",
        )

    # 404 on unknown cluster is deliberate — same shape as `/clusters/{id}` in
    # REL-06 so the frontend can handle both endpoints uniformly.
    cluster_exists = (
        await db.execute(
            select(NewsCluster.id).where(NewsCluster.id == cluster_id)
        )
    ).scalar_one_or_none()
    if cluster_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="cluster not found"
        )

    cached = (
        await db.execute(
            select(ImpactAssessment).where(
                ImpactAssessment.cluster_id == cluster_id,
                ImpactAssessment.user_id == user.user_id,
                ImpactAssessment.portfolio_id == portfolio.id,
            )
        )
    ).scalar_one_or_none()
    if cached is not None:
        return ImpactRead.model_validate(cached)

    score = await _load_relevance_score(
        db, cluster_id, user.user_id, portfolio.id
    )
    if score is None or score < _IMPACT_MIN_SCORE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"cluster relevance is below the impact threshold "
                f"(need score >= {_IMPACT_MIN_SCORE})"
            ),
        )

    await enqueue(cluster_id, user.user_id, portfolio.id, False)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "generating",
            "poll_url": _poll_url(request, cluster_id),
        },
    )


@router.post("/{cluster_id}/impact/generate", name="generate_impact")
async def generate_impact(
    cluster_id: UUID,
    request: Request,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
    enqueue: EnqueueFn = Depends(get_impact_enqueue),
):
    portfolio = await _active_portfolio(user.user_id, db)
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active portfolio",
        )

    cluster_exists = (
        await db.execute(
            select(NewsCluster.id).where(NewsCluster.id == cluster_id)
        )
    ).scalar_one_or_none()
    if cluster_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="cluster not found"
        )

    score = await _load_relevance_score(
        db, cluster_id, user.user_id, portfolio.id
    )
    if score is None or score < _IMPACT_MIN_SCORE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"cluster relevance is below the impact threshold "
                f"(need score >= {_IMPACT_MIN_SCORE})"
            ),
        )

    await enqueue(cluster_id, user.user_id, portfolio.id, True)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "generating",
            "poll_url": _poll_url(request, cluster_id),
        },
    )
