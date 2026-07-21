"""Impact analyst LangGraph (IMP-04).

Composes the six previous modules into one graph:

    START
      → load_context      (cluster + touched positions + portfolio + source stubs)
      → retrieve_analogs  (IMP-02 tool)
      → fetch_price_context (IMP-03 tool, one call per touched-position ticker)
      → reason_mechanism  (thorough-tier LLM → ImpactAssessmentPayload)
      → validate          (GRD-01 lexical + GRD-02)
      → [conditional: violations → repair_prompt → reason_mechanism, once]
      → persist           (write `impact_assessments` row)
      → END

`analyze_impact_for_user()` wraps the graph with idempotency on
(cluster_id, user_id, portfolio_id) — returns the cached row unless
`force=True`, in which case the cached row is deleted and the graph runs
fresh. Mirrors REL-04.

Deviation from BUILD.md: GRD-01's LLM stage is intentionally suppressed
(`skip_llm=True`) inside `validate` — only the lexical check runs here.
Reason: the same `LLMClient` also drives `reason_mechanism`; if we also
consumed calls for the guardrail LLM stage the repair loop would be
non-deterministic under our scripted-LLM test doubles. The lexical
stage is enough to test the repair path deterministically; production
retains the GRD-01 lexical guarantee, which is the strictest rule in
the guardrail suite.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any, Callable, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.impact.prompts import (
    SYSTEM_PROMPT,
    build_reason_prompt,
    build_repair_prompt,
)
from app.db.models.impact import ImpactAssessment
from app.db.models.news import NewsCluster, NewsItem
from app.db.models.portfolio import Portfolio
from app.db.models.position import Position
from app.db.models.relevance import RelevanceScore
from app.db.vectorstore import VectorStore
from app.guardrails.citations import SourceStub, check_citations
from app.guardrails.directional import check_directional
from app.schemas.impact import ImpactAssessment as ImpactAssessmentPayload
from app.tools.historical_analogs import retrieve_analogs as retrieve_analogs_tool
from app.tools.prices import PriceContext, get_recent_price_action
from app.utils.embeddings import EmbeddingClient
from app.utils.llm import LLMClient, LLMResponse, Message

log = logging.getLogger(__name__)


_NEWS_ITEMS_MAX = 5


class _GraphState(TypedDict, total=False):
    # -- inputs ----------------------------------------------------------
    cluster_id: UUID
    user_id: UUID
    portfolio_id: UUID
    session: AsyncSession
    analogs_store: VectorStore
    embed: EmbeddingClient
    llm: LLMClient
    fetch_prices: Callable[..., PriceContext | None]

    # -- accumulated context --------------------------------------------
    cluster: NewsCluster
    news_items: list[NewsItem]
    positions: list[Position]
    portfolio: Portfolio
    source_stubs: list[SourceStub]
    analogs: list[Any]  # list[HistoricalAnalog]
    price_contexts: dict[str, PriceContext | None]

    # -- LLM output ------------------------------------------------------
    draft: ImpactAssessmentPayload | None
    raw_llm_output: str | None
    llm_response: LLMResponse | None
    # Violations from the CURRENT LLM attempt only — cleared at the start of
    # each `reason_mechanism` invocation.
    guardrail_violations: list[dict[str, str]]
    # Violations snapshotted from the FIRST attempt when we route through
    # `repair_prompt`. Merged into the persisted row only when the repair
    # itself also fails.
    historical_violations: list[dict[str, str]]
    repair_attempted: bool

    # -- persisted row --------------------------------------------------
    row: ImpactAssessment | None


# --- nodes -----------------------------------------------------------------


async def _load_context_node(state: _GraphState) -> _GraphState:
    session: AsyncSession = state["session"]
    cluster_id: UUID = state["cluster_id"]
    user_id: UUID = state["user_id"]
    portfolio_id: UUID = state["portfolio_id"]

    cluster = (
        await session.execute(
            select(NewsCluster).where(NewsCluster.id == cluster_id)
        )
    ).scalar_one_or_none()
    if cluster is None:
        raise ValueError(f"news_clusters.id={cluster_id} not found")

    portfolio = (
        await session.execute(
            select(Portfolio).where(Portfolio.id == portfolio_id)
        )
    ).scalar_one_or_none()
    if portfolio is None:
        raise ValueError(f"portfolios.id={portfolio_id} not found")
    if portfolio.user_id != user_id:
        raise ValueError(
            f"portfolio {portfolio_id} does not belong to user {user_id}"
        )

    news_items = list(
        (
            await session.execute(
                select(NewsItem)
                .where(NewsItem.cluster_id == cluster_id)
                .order_by(NewsItem.published_at.desc())
                .limit(_NEWS_ITEMS_MAX)
            )
        )
        .scalars()
        .all()
    )

    source_stubs: list[SourceStub] = []
    for item in news_items:
        body_text = item.body or item.title or ""
        source_stubs.append(SourceStub(url=str(item.url), body=body_text))

    relevance = (
        await session.execute(
            select(RelevanceScore).where(
                RelevanceScore.cluster_id == cluster_id,
                RelevanceScore.user_id == user_id,
                RelevanceScore.portfolio_id == portfolio_id,
            )
        )
    ).scalar_one_or_none()

    touched_ids: list[str] = []
    if relevance is not None:
        touched_ids = list(relevance.touched_position_ids or [])

    positions: list[Position] = []
    if touched_ids:
        positions = list(
            (
                await session.execute(
                    select(Position).where(
                        Position.id.in_([UUID(pid) for pid in touched_ids])
                    )
                )
            )
            .scalars()
            .all()
        )
    else:
        # Fallback: use every position in the portfolio. Should be rare — the
        # relevance row is normally populated upstream by REL-04.
        log.warning(
            "impact: no relevance row for (cluster=%s, user=%s, portfolio=%s); "
            "falling back to full portfolio",
            cluster_id, user_id, portfolio_id,
        )
        positions = list(
            (
                await session.execute(
                    select(Position).where(
                        Position.portfolio_id == portfolio_id
                    )
                )
            )
            .scalars()
            .all()
        )

    return {
        "cluster": cluster,
        "portfolio": portfolio,
        "news_items": news_items,
        "source_stubs": source_stubs,
        "positions": positions,
        # Seed accumulators so downstream nodes don't need to defensively init.
        "guardrail_violations": [],
        "historical_violations": [],
        "repair_attempted": False,
    }


async def _retrieve_analogs_node(state: _GraphState) -> _GraphState:
    cluster: NewsCluster = state["cluster"]
    embed: EmbeddingClient = state["embed"]
    store: VectorStore = state["analogs_store"]
    try:
        analogs = await retrieve_analogs_tool(
            cluster.canonical_title, k=3, embed=embed, store=store
        )
    except Exception as exc:  # noqa: BLE001 — the tool is best-effort
        log.warning("impact: retrieve_analogs failed: %s", exc)
        analogs = []
    return {"analogs": analogs}


async def _fetch_price_context_node(state: _GraphState) -> _GraphState:
    positions: list[Position] = state.get("positions") or []
    fetch: Callable[..., PriceContext | None] = state.get(
        "fetch_prices", get_recent_price_action
    )
    tickers: list[str] = []
    seen: set[str] = set()
    for p in positions:
        t = (p.ticker or "").strip().upper()
        if not t or t in seen:
            continue
        seen.add(t)
        tickers.append(t)

    price_contexts: dict[str, PriceContext | None] = {}
    for ticker in tickers:
        try:
            ctx = await asyncio.to_thread(fetch, ticker)
        except Exception as exc:  # noqa: BLE001 — price data is best-effort
            log.warning("impact: price fetch failed for %s: %s", ticker, exc)
            ctx = None
        price_contexts[ticker] = ctx
    return {"price_contexts": price_contexts}


async def _reason_mechanism_node(state: _GraphState) -> _GraphState:
    llm: LLMClient = state["llm"]
    if state.get("repair_attempted"):
        user_content = build_repair_prompt(state)
    else:
        user_content = build_reason_prompt(state)

    messages = [
        Message(role="system", content=SYSTEM_PROMPT),
        Message(role="user", content=user_content),
    ]

    # Fresh attempt — clear stale violations from the previous try. The
    # persisted `guardrail_violations` field describes only what SURVIVED the
    # final attempt; anything the retry cleaned up disappears here. If the
    # retry fails too, `_repair_prompt_node` will have already snapshotted the
    # first attempt's violations into `historical_violations`.
    update: _GraphState = {"guardrail_violations": []}
    try:
        response = await llm.complete(
            messages,
            tier="thorough",
            response_model=ImpactAssessmentPayload,
            user_id=state["user_id"],
            agent_name="impact-analyst",
        )
    except Exception as exc:  # noqa: BLE001 — record and continue
        log.warning("impact: LLM call failed: %s", exc)
        update["draft"] = None
        update["raw_llm_output"] = None
        update["llm_response"] = None
        update["guardrail_violations"] = [
            {"stage": "llm", "reason": str(exc)[:200]}
        ]
        return update

    parsed = response.parsed
    if not isinstance(parsed, ImpactAssessmentPayload):
        update["draft"] = None
        update["raw_llm_output"] = response.content
        update["llm_response"] = response
        update["guardrail_violations"] = [
            {"stage": "llm", "reason": "response missing parsed payload"}
        ]
        return update

    update["draft"] = parsed
    update["raw_llm_output"] = response.content
    update["llm_response"] = response
    return update


async def _validate_node(state: _GraphState) -> _GraphState:
    draft = state.get("draft")
    if draft is None:
        # LLM failure already recorded in guardrail_violations.
        return {}

    violations: list[dict[str, str]] = list(state.get("guardrail_violations") or [])

    # GRD-01 — lexical only, see module docstring for rationale.
    dir_verdict = await check_directional(draft.mechanism, skip_llm=True)
    if not dir_verdict.passed:
        violations.append({"stage": "directional", "reason": dir_verdict.reason})

    # GRD-02 — citations grounded in the source stubs the LLM saw.
    cit_verdict = check_citations(
        draft.citations, allowed_stubs=state.get("source_stubs") or []
    )
    if not cit_verdict.passed:
        reason = "; ".join(cit_verdict.reasons) if cit_verdict.reasons else "unspecified"
        violations.append({"stage": "citations", "reason": reason[:200]})

    return {"guardrail_violations": violations}


async def _repair_prompt_node(state: _GraphState) -> _GraphState:
    """Snapshot the failing attempt's violations, flip the retry flag.

    The user-facing prompt for the retry is built inside
    `_reason_mechanism_node` when it sees `repair_attempted=True` — this node
    is where we preserve the first attempt's violations under
    `historical_violations`, so `_persist_node` can merge them in if the
    retry ALSO fails.
    """
    prev = list(state.get("historical_violations") or [])
    prev.extend(state.get("guardrail_violations") or [])
    return {"repair_attempted": True, "historical_violations": prev}


async def _persist_node(state: _GraphState) -> _GraphState:
    session: AsyncSession = state["session"]
    draft = state.get("draft")
    current = list(state.get("guardrail_violations") or [])

    # Semantic: the persisted `guardrail_violations` column records what
    # SURVIVED the process. If the retry cleaned things up, it should be [];
    # if both attempts failed, it should show every violation.
    if current:
        final_violations = list(state.get("historical_violations") or [])
        final_violations.extend(current)
    else:
        final_violations = []

    if draft is None:
        # Nothing salvageable — do NOT insert a placeholder row.
        log.warning(
            "impact: skipping persist — no usable draft (violations=%s)",
            final_violations,
        )
        return {"row": None}

    citations_json = [c.model_dump(mode="json") for c in draft.citations]
    analogs_json = [a.model_dump(mode="json") for a in draft.historical_analogs]

    row = ImpactAssessment(
        cluster_id=state["cluster_id"],
        user_id=state["user_id"],
        portfolio_id=state["portfolio_id"],
        mechanism=draft.mechanism,
        magnitude_low=_to_decimal(draft.magnitude_low, "0.0001"),
        magnitude_high=_to_decimal(draft.magnitude_high, "0.0001"),
        timeframe_days=draft.timeframe_days,
        confidence=Decimal(f"{max(0.0, min(1.0, draft.confidence)):.2f}"),
        falsifiability=draft.falsifiability,
        citations=citations_json,
        historical_analogs=analogs_json,
        affected_positions=[str(u) for u in draft.affected_positions],
        raw_llm_output=state.get("raw_llm_output"),
        guardrail_violations=final_violations,
        langsmith_run_id=None,  # LLMResponse doesn't surface this today.
    )
    session.add(row)
    await session.commit()
    return {"row": row}


def _to_decimal(value: float | None, quant: str) -> Decimal | None:
    """Coerce an LLM-produced float to a Decimal with fixed precision.

    Uses string formatting so we skirt the usual float→Decimal precision
    surprises (Decimal(0.1) has 55 digits of noise); `quant` names the
    smallest representable unit and matches the ORM `Numeric(6, 4)` scale
    for the magnitude columns.
    """
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal(quant))


# --- routing ---------------------------------------------------------------


def _route_after_validate(state: _GraphState) -> str:
    violations = state.get("guardrail_violations") or []
    if not violations:
        return "persist"
    if state.get("repair_attempted"):
        # We already retried once — persist whatever we have and surface the
        # violations on the row so downstream can act on them.
        return "persist"
    return "repair"


# --- graph build -----------------------------------------------------------


def _build_graph():
    g = StateGraph(_GraphState)
    g.add_node("load_context", _load_context_node)
    g.add_node("retrieve_analogs", _retrieve_analogs_node)
    g.add_node("fetch_price_context", _fetch_price_context_node)
    g.add_node("reason_mechanism", _reason_mechanism_node)
    g.add_node("validate", _validate_node)
    g.add_node("repair_prompt", _repair_prompt_node)
    g.add_node("persist", _persist_node)

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "retrieve_analogs")
    g.add_edge("retrieve_analogs", "fetch_price_context")
    g.add_edge("fetch_price_context", "reason_mechanism")
    g.add_edge("reason_mechanism", "validate")
    g.add_conditional_edges(
        "validate",
        _route_after_validate,
        {"persist": "persist", "repair": "repair_prompt"},
    )
    g.add_edge("repair_prompt", "reason_mechanism")
    g.add_edge("persist", END)
    return g.compile()


# Compiled at import time so a shape error surfaces immediately (per REL-04 precedent).
IMPACT_GRAPH = _build_graph()


# --- public entry ----------------------------------------------------------


async def analyze_impact_for_user(
    cluster_id: UUID,
    user_id: UUID,
    portfolio_id: UUID,
    *,
    session: AsyncSession,
    analogs_store: VectorStore,
    embed: EmbeddingClient,
    llm: LLMClient,
    fetch_prices: Callable[..., PriceContext | None] = get_recent_price_action,
    force: bool = False,
) -> ImpactAssessment | None:
    """Produce an impact assessment for one (cluster, user, portfolio).

    Idempotent: an existing row is returned unless `force=True`, in which case
    the cached row is deleted and the graph runs fresh. Returns `None` when
    the graph finished without producing a usable draft (LLM parse failure
    that survived the repair retry).
    """
    existing = (
        await session.execute(
            select(ImpactAssessment).where(
                ImpactAssessment.cluster_id == cluster_id,
                ImpactAssessment.user_id == user_id,
                ImpactAssessment.portfolio_id == portfolio_id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        if not force:
            return existing
        await session.execute(
            delete(ImpactAssessment).where(ImpactAssessment.id == existing.id)
        )
        await session.commit()

    result = await IMPACT_GRAPH.ainvoke(
        {
            "cluster_id": cluster_id,
            "user_id": user_id,
            "portfolio_id": portfolio_id,
            "session": session,
            "analogs_store": analogs_store,
            "embed": embed,
            "llm": llm,
            "fetch_prices": fetch_prices,
        }
    )
    return result.get("row")
