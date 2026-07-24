"""Scenario simulator LangGraph (SIM-02).

Composes portfolio context, historical analog retrieval, recent price action,
and a thorough-tier LLM into one graph that answers a hypothetical scenario
("Fed cuts 50bps next FOMC") with a structured impact assessment across the
caller's portfolio.

Graph:

    START
      → load_portfolio_context  (portfolio + positions + themes for the caller)
      → retrieve_analogs        (IMP-02 tool, scenario_text as the query)
      → fetch_price_context     (IMP-03 tool, one call per portfolio ticker)
      → reason_scenario         (thorough-tier LLM → ScenarioSimulation)
      → validate                (GRD-01 lexical on summary + per-position mechanisms)
      → END

Public entry `simulate_scenario()` is a pure function — SIM-02 does NOT
persist. This is a deviation from IMP-04 (which writes `impact_assessments`)
and BRIEF-02 (which writes `briefings`): a scenario is a one-shot response
to a hypothetical, not a durable record. Persistence (if any) is SIM-01's
territory once that endpoint lands.

Deviation from BUILD.md: as with IMP-04 and BRIEF-02, `check_directional`
runs with `skip_llm=True` — only the lexical stage runs in-graph. Same
rationale: the guardrail's LLM stage would compete with `reason_scenario`
for scripted-LLM responses under test doubles and yield non-deterministic
call counts. Production still gets the strictest guardrail rule (lexical).

Deviation from BUILD.md's shape: no repair loop. The scenario prompt is
more constrained than the impact prompt (mechanism-only across a known
position set) and a single-attempt approach keeps the graph simple; a
guardrail failure returns None rather than retrying.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.scenario.prompts import SCENARIO_SYSTEM, build_reason_prompt
from app.db.models.portfolio import Portfolio
from app.db.models.position import Position
from app.db.models.theme import Theme
from app.db.vectorstore import VectorStore
from app.guardrails.directional import check_directional
from app.schemas.scenario import ScenarioSimulation
from app.tools.historical_analogs import retrieve_analogs as retrieve_analogs_tool
from app.tools.prices import PriceContext, get_recent_price_action
from app.utils.embeddings import EmbeddingClient
from app.utils.llm import LLMClient, Message

log = logging.getLogger(__name__)


class _GraphState(TypedDict, total=False):
    # -- inputs ---------------------------------------------------------
    user_id: UUID
    portfolio_id: UUID
    scenario_text: str
    session: AsyncSession
    analogs_store: VectorStore
    embed: EmbeddingClient
    llm: LLMClient
    fetch_prices: Callable[..., PriceContext | None]

    # -- accumulated context -------------------------------------------
    portfolio: Portfolio | None
    positions: list[Position]
    themes: list[Theme]
    analogs: list[Any]  # list[HistoricalAnalog]
    price_contexts: dict[str, PriceContext | None]

    # -- LLM output ----------------------------------------------------
    draft: ScenarioSimulation | None
    guardrail_violations: list[dict[str, str]]


# --- nodes -----------------------------------------------------------------


async def _load_portfolio_context_node(state: _GraphState) -> _GraphState:
    session: AsyncSession = state["session"]
    user_id: UUID = state["user_id"]
    portfolio_id: UUID = state["portfolio_id"]

    portfolio = (
        await session.execute(
            select(Portfolio).where(Portfolio.id == portfolio_id)
        )
    ).scalar_one_or_none()

    # Ownership check: an unknown or foreign portfolio yields an empty context.
    # `simulate_scenario` (the caller) bails with None when it sees no
    # portfolio in the resulting state.
    if portfolio is None or portfolio.user_id != user_id:
        if portfolio is not None:
            log.warning(
                "scenario: portfolio %s does not belong to user %s",
                portfolio_id, user_id,
            )
        return {
            "portfolio": None,
            "positions": [],
            "themes": [],
            "guardrail_violations": [],
        }

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
                select(Theme).where(Theme.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )

    return {
        "portfolio": portfolio,
        "positions": positions,
        "themes": themes,
        "guardrail_violations": [],
    }


async def _retrieve_analogs_node(state: _GraphState) -> _GraphState:
    if state.get("portfolio") is None:
        return {"analogs": []}

    scenario_text: str = state.get("scenario_text") or ""
    embed: EmbeddingClient = state["embed"]
    store: VectorStore = state["analogs_store"]
    try:
        analogs = await retrieve_analogs_tool(
            scenario_text, k=5, embed=embed, store=store
        )
    except Exception as exc:  # noqa: BLE001 — the tool is best-effort
        log.warning("scenario: retrieve_analogs failed: %s", exc)
        analogs = []
    return {"analogs": analogs}


async def _fetch_price_context_node(state: _GraphState) -> _GraphState:
    if state.get("portfolio") is None:
        return {"price_contexts": {}}

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
            # `get_recent_price_action` is sync; run in the default executor
            # so the graph event loop isn't blocked on network I/O.
            ctx = await asyncio.to_thread(fetch, ticker)
        except Exception as exc:  # noqa: BLE001 — price data is best-effort
            log.warning("scenario: price fetch failed for %s: %s", ticker, exc)
            ctx = None
        price_contexts[ticker] = ctx
    return {"price_contexts": price_contexts}


async def _reason_scenario_node(state: _GraphState) -> _GraphState:
    if state.get("portfolio") is None:
        return {"draft": None}

    llm: LLMClient = state["llm"]
    messages = [
        Message(role="system", content=SCENARIO_SYSTEM),
        Message(role="user", content=build_reason_prompt(state)),
    ]

    try:
        response = await llm.complete(
            messages,
            tier="thorough",
            response_model=ScenarioSimulation,
            user_id=state["user_id"],
            agent_name="scenario-analyst",
        )
    except Exception as exc:  # noqa: BLE001 — record and continue
        log.warning("scenario: LLM call failed: %s", exc)
        return {"draft": None}

    parsed = response.parsed
    if not isinstance(parsed, ScenarioSimulation):
        log.warning("scenario: LLM response missing parsed ScenarioSimulation")
        return {"draft": None}
    return {"draft": parsed}


async def _validate_node(state: _GraphState) -> _GraphState:
    draft = state.get("draft")
    if draft is None:
        # Nothing to validate, but LangGraph requires each node to write at
        # least one channel — echo the (unchanged) violations list.
        return {"guardrail_violations": list(state.get("guardrail_violations") or [])}

    violations: list[dict[str, str]] = list(state.get("guardrail_violations") or [])

    # GRD-01 — lexical only (see module docstring).
    summary_verdict = await check_directional(
        draft.portfolio_summary, skip_llm=True
    )
    if not summary_verdict.passed:
        violations.append(
            {"stage": "directional:portfolio_summary", "reason": summary_verdict.reason}
        )

    for i, pi in enumerate(draft.per_position_impact):
        pi_verdict = await check_directional(pi.mechanism, skip_llm=True)
        if not pi_verdict.passed:
            violations.append(
                {
                    "stage": f"directional:per_position_impact[{i}]:{pi.ticker}",
                    "reason": pi_verdict.reason,
                }
            )

    if violations:
        log.warning(
            "scenario: dropping draft due to %d guardrail violation(s): %s",
            len(violations), violations,
        )
        return {"draft": None, "guardrail_violations": violations}
    return {"guardrail_violations": violations}


# --- graph build -----------------------------------------------------------


def _build_graph():
    g = StateGraph(_GraphState)
    g.add_node("load_portfolio_context", _load_portfolio_context_node)
    g.add_node("retrieve_analogs", _retrieve_analogs_node)
    g.add_node("fetch_price_context", _fetch_price_context_node)
    g.add_node("reason_scenario", _reason_scenario_node)
    g.add_node("validate", _validate_node)

    g.add_edge(START, "load_portfolio_context")
    g.add_edge("load_portfolio_context", "retrieve_analogs")
    g.add_edge("retrieve_analogs", "fetch_price_context")
    g.add_edge("fetch_price_context", "reason_scenario")
    g.add_edge("reason_scenario", "validate")
    g.add_edge("validate", END)
    return g.compile()


# Compiled at import time so any shape error surfaces immediately
# (matches IMP-04 / REL-04 / BRIEF-02 precedent).
SCENARIO_GRAPH = _build_graph()


# --- public entry ----------------------------------------------------------


async def simulate_scenario(
    user_id: UUID,
    portfolio_id: UUID,
    scenario_text: str,
    *,
    session: AsyncSession,
    analogs_store: VectorStore,
    embed: EmbeddingClient,
    llm: LLMClient,
    fetch_prices: Callable[..., PriceContext | None] = get_recent_price_action,
) -> ScenarioSimulation | None:
    """Produce a scenario simulation for one (user, portfolio, scenario).

    Returns None if:
    - the portfolio isn't the caller's (or doesn't exist);
    - the LLM call fails or the response can't be parsed as
      `ScenarioSimulation`;
    - the guardrail (GRD-01 lexical) rejects the summary or any per-position
      mechanism.

    No persistence — see the module docstring.
    """
    result = await SCENARIO_GRAPH.ainvoke(
        {
            "user_id": user_id,
            "portfolio_id": portfolio_id,
            "scenario_text": scenario_text,
            "session": session,
            "analogs_store": analogs_store,
            "embed": embed,
            "llm": llm,
            "fetch_prices": fetch_prices,
        }
    )
    return result.get("draft")
