"""Relevance graph — LangGraph composition of prefilter + classifier (REL-04).

Flow:

    START → prefilter → [conditional: passed?] → END
                     → classifier → END

The prefilter (REL-02) either short-circuits with a persisted `stage='prefilter'`
row or hands a shortlist to the classifier (REL-03), which writes a
`stage='classifier'` row.

`score_cluster_for_user()` wraps the graph with an idempotency check keyed on
`(cluster_id, user_id, portfolio_id)` — the unique constraint on
`relevance_scores`. On a cache hit the cached row is returned without invoking
the LLM. `force=True` deletes the cached row and re-runs the graph.
"""
from __future__ import annotations

import logging
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.relevance.classifier import run_classifier
from app.agents.relevance.prefilter import PrefilterResult, run_prefilter
from app.db.models.relevance import RelevanceScore
from app.db.vectorstore import VectorStore
from app.utils.embeddings import EmbeddingClient
from app.utils.llm import LLMClient

log = logging.getLogger(__name__)


class _GraphState(TypedDict, total=False):
    cluster_id: UUID
    user_id: UUID
    portfolio_id: UUID
    session: AsyncSession
    news_store: VectorStore
    themes_store: VectorStore
    embed: EmbeddingClient
    llm: LLMClient
    agent_name: str
    prefilter_result: PrefilterResult
    row: RelevanceScore


async def _prefilter_node(state: _GraphState) -> _GraphState:
    result = await run_prefilter(
        cluster_id=state["cluster_id"],
        portfolio_id=state["portfolio_id"],
        session=state["session"],
        news_store=state["news_store"],
        themes_store=state["themes_store"],
        embed=state["embed"],
    )
    update: _GraphState = {"prefilter_result": result}
    if not result.passed and result.persisted_row is not None:
        update["row"] = result.persisted_row
    return update


async def _classifier_node(state: _GraphState) -> _GraphState:
    pre = state["prefilter_result"]
    row = await run_classifier(
        cluster_id=state["cluster_id"],
        portfolio_id=state["portfolio_id"],
        candidate_position_ids=pre.candidate_position_ids,
        candidate_theme_ids=pre.candidate_theme_ids,
        session=state["session"],
        llm=state["llm"],
        agent_name=state.get("agent_name", "relevance-classifier"),
    )
    return {"row": row}


def _route_after_prefilter(state: _GraphState) -> str:
    return "classifier" if state["prefilter_result"].passed else "end"


def _build_graph():
    g = StateGraph(_GraphState)
    g.add_node("prefilter", _prefilter_node)
    g.add_node("classifier", _classifier_node)
    g.add_edge(START, "prefilter")
    g.add_conditional_edges(
        "prefilter",
        _route_after_prefilter,
        {"classifier": "classifier", "end": END},
    )
    g.add_edge("classifier", END)
    return g.compile()


# Compiled at import time so a shape error surfaces immediately (per acceptance).
RELEVANCE_GRAPH = _build_graph()


async def score_cluster_for_user(
    cluster_id: UUID,
    user_id: UUID,
    portfolio_id: UUID,
    *,
    session: AsyncSession,
    news_store: VectorStore,
    themes_store: VectorStore,
    embed: EmbeddingClient,
    llm: LLMClient,
    force: bool = False,
    agent_name: str = "relevance-classifier",
) -> RelevanceScore:
    """Score one cluster for one (user, portfolio) with idempotency.

    Returns the cached row when one already exists for the key, unless
    `force=True` — in which case the cached row is deleted and the graph
    runs fresh.
    """
    existing = (
        await session.execute(
            select(RelevanceScore).where(
                RelevanceScore.cluster_id == cluster_id,
                RelevanceScore.user_id == user_id,
                RelevanceScore.portfolio_id == portfolio_id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        if not force:
            return existing
        await session.execute(
            delete(RelevanceScore).where(RelevanceScore.id == existing.id)
        )
        await session.commit()

    result = await RELEVANCE_GRAPH.ainvoke(
        {
            "cluster_id": cluster_id,
            "user_id": user_id,
            "portfolio_id": portfolio_id,
            "session": session,
            "news_store": news_store,
            "themes_store": themes_store,
            "embed": embed,
            "llm": llm,
            "agent_name": agent_name,
        }
    )
    row = result.get("row")
    if row is None:
        raise RuntimeError(
            "relevance graph completed without producing a RelevanceScore row"
        )
    return row
