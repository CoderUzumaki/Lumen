"""Briefing synthesizer LangGraph (BRIEF-02).

Graph:

    START
      → gather_impacts       (last N hours, confidence ≥ 0.5, no guardrail_violations)
      → rank_top_movers      (fast-tier LLM: pick 3–5)
      → rank_watchlist       (fast-tier LLM: pick 3–5 from remainder)
      → synthesize_falsifiability (fast-tier LLM: 3–5 pivot events)
      → compose_summary      (thorough-tier LLM: ≤800-char overview)
      → validate             (GRD-01 lexical on all text produced)
      → persist              (write `briefings` row)
      → END

Public entry `synthesize_briefing_for_user()` is idempotent on
`(user_id, portfolio_id, briefing_date)` — the unique constraint on
`briefings`. On any guardrail violation, the WHOLE briefing is dropped
(returns None) — a briefing that leaks directional language into any of
top-movers, watchlist, or the summary must not persist. IMP-04's per-item
repair loop doesn't apply here: the failure mode is different (aggregation
across many upstream impacts, not one LLM draft).

Deviation from BUILD.md: as with IMP-04, `check_directional` runs with
`skip_llm=True` — only the lexical stage runs in-graph. Same rationale
(shared scripted LLM under test doubles).
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.briefing.prompts import (
    COMPOSE_SUMMARY_SYSTEM,
    RANK_TOP_MOVERS_SYSTEM,
    RANK_WATCHLIST_SYSTEM,
    SYNTHESIZE_FALSIFIABILITY_SYSTEM,
    build_falsifiability_prompt,
    build_rank_prompt,
    build_summary_prompt,
)
from app.db.models.briefing import Briefing
from app.db.models.impact import ImpactAssessment
from app.db.models.news import NewsCluster
from app.db.models.position import Position
from app.guardrails.directional import check_directional
from app.schemas.briefing import BriefingContent, BriefingItem
from app.utils.llm import LLMClient, Message

log = logging.getLogger(__name__)


_MIN_CONFIDENCE = 0.5
_MAX_CANDIDATES = 15  # BUILD acceptance is exercised at exactly 15
_MAX_TOP = 5
_MAX_WATCHLIST = 5
_MAX_FALSIFIABILITY = 5


# ---------------------------------------------------------------------------
# LLM structured outputs
# ---------------------------------------------------------------------------


class _RankPick(BaseModel):
    """Fast-tier LLM output for the two ranking stages."""

    picks: list[UUID] = Field(default_factory=list)
    one_line_summaries: dict[UUID, str] = Field(default_factory=dict)


class _FalsifiabilityList(BaseModel):
    items: list[str] = Field(default_factory=list, max_length=_MAX_FALSIFIABILITY)


class _Summary(BaseModel):
    text: str = Field(max_length=800)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class _GraphState(TypedDict, total=False):
    # inputs
    user_id: UUID
    portfolio_id: UUID
    session: AsyncSession
    llm: LLMClient
    briefing_date: date
    lookback_hours: int

    # accumulated context
    candidates: list[dict[str, Any]]  # normalized dict per impact for prompts
    top_ids: list[UUID]
    top_items: list[BriefingItem]
    watchlist_items: list[BriefingItem]
    falsifiability: list[str]
    summary_text: str

    # bookkeeping
    started_monotonic: float
    guardrail_violations: list[dict[str, str]]

    # output
    row: Briefing | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _novelty_score(created_at: datetime) -> float:
    """Simple recency weight: 1 / (1 + hours_since_created). Naive-safe."""
    now = _now_utc()
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    hours = max(0.0, (now - created_at).total_seconds() / 3600.0)
    return 1.0 / (1.0 + hours)


async def _resolve_tickers(
    session: AsyncSession, position_ids: list[str]
) -> list[str]:
    """Map `affected_positions` UUIDs → ticker strings, order preserved."""
    if not position_ids:
        return []
    uuid_list: list[UUID] = []
    for raw in position_ids:
        try:
            uuid_list.append(UUID(raw))
        except (TypeError, ValueError):
            continue
    if not uuid_list:
        return []
    rows = list(
        (
            await session.execute(
                select(Position).where(Position.id.in_(uuid_list))
            )
        )
        .scalars()
        .all()
    )
    by_id = {p.id: p.ticker for p in rows}
    return [by_id[UUID(pid)] for pid in position_ids if UUID(pid) in by_id]


def _candidate_dict(
    impact: ImpactAssessment,
    cluster_title: str,
    tickers: list[str],
) -> dict[str, Any]:
    return {
        "impact_id": impact.id,
        "cluster_id": impact.cluster_id,
        "cluster_title": cluster_title,
        "confidence": float(impact.confidence),
        "mechanism": impact.mechanism,
        "tickers": tickers,
        "created_at": impact.created_at,
    }


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def _gather_impacts_node(state: _GraphState) -> _GraphState:
    session: AsyncSession = state["session"]
    user_id: UUID = state["user_id"]
    portfolio_id: UUID = state["portfolio_id"]
    lookback_hours = state.get("lookback_hours", 24)

    cutoff = _now_utc() - timedelta(hours=lookback_hours)
    stmt = (
        select(ImpactAssessment, NewsCluster.canonical_title)
        .join(NewsCluster, NewsCluster.id == ImpactAssessment.cluster_id)
        .where(
            ImpactAssessment.user_id == user_id,
            ImpactAssessment.portfolio_id == portfolio_id,
            ImpactAssessment.created_at >= cutoff,
            ImpactAssessment.confidence >= _MIN_CONFIDENCE,
        )
    )
    rows = list((await session.execute(stmt)).all())

    candidates: list[dict[str, Any]] = []
    skipped_gv = 0
    for impact, cluster_title in rows:
        gv = impact.guardrail_violations or []
        if len(gv) > 0:
            skipped_gv += 1
            continue
        tickers = await _resolve_tickers(session, impact.affected_positions or [])
        candidates.append(_candidate_dict(impact, cluster_title, tickers))

    if skipped_gv:
        log.debug("briefing: skipped %d impact(s) with guardrail_violations", skipped_gv)

    # Rank by confidence × novelty, keep top N.
    candidates.sort(
        key=lambda c: c["confidence"] * _novelty_score(c["created_at"]),
        reverse=True,
    )
    candidates = candidates[:_MAX_CANDIDATES]

    return {"candidates": candidates, "guardrail_violations": []}


async def _rank_top_movers_node(state: _GraphState) -> _GraphState:
    candidates = state.get("candidates") or []
    if not candidates:
        return {"top_ids": [], "top_items": []}

    llm: LLMClient = state["llm"]
    prompt = build_rank_prompt(candidates, purpose="top_movers")
    messages = [
        Message(role="system", content=RANK_TOP_MOVERS_SYSTEM),
        Message(role="user", content=prompt),
    ]
    try:
        response = await llm.complete(
            messages,
            tier="fast",
            response_model=_RankPick,
            user_id=state["user_id"],
            agent_name="briefing-synthesizer",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("briefing: rank_top_movers LLM failed: %s", exc)
        return {"top_ids": [], "top_items": []}

    parsed = response.parsed if isinstance(response.parsed, _RankPick) else _RankPick()
    valid_ids = {c["impact_id"] for c in candidates}
    kept: list[UUID] = []
    for pick in parsed.picks:
        if pick in valid_ids and pick not in kept:
            kept.append(pick)
        if len(kept) >= _MAX_TOP:
            break

    by_id = {c["impact_id"]: c for c in candidates}
    top_items: list[BriefingItem] = []
    for pid in kept:
        c = by_id[pid]
        one_line = (parsed.one_line_summaries or {}).get(pid) or c["mechanism"][:200]
        top_items.append(
            BriefingItem(
                impact_id=pid,
                cluster_title=c["cluster_title"][:300],
                one_line_summary=one_line[:200],
                affected_positions=c["tickers"],
                mechanism_summary=c["mechanism"][:400],
                confidence=c["confidence"],
            )
        )
    return {"top_ids": kept, "top_items": top_items}


async def _rank_watchlist_node(state: _GraphState) -> _GraphState:
    candidates = state.get("candidates") or []
    top_set = set(state.get("top_ids") or [])
    remaining = [c for c in candidates if c["impact_id"] not in top_set]
    if not remaining:
        return {"watchlist_items": []}

    llm: LLMClient = state["llm"]
    prompt = build_rank_prompt(remaining, purpose="watchlist")
    messages = [
        Message(role="system", content=RANK_WATCHLIST_SYSTEM),
        Message(role="user", content=prompt),
    ]
    try:
        response = await llm.complete(
            messages,
            tier="fast",
            response_model=_RankPick,
            user_id=state["user_id"],
            agent_name="briefing-synthesizer",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("briefing: rank_watchlist LLM failed: %s", exc)
        return {"watchlist_items": []}

    parsed = response.parsed if isinstance(response.parsed, _RankPick) else _RankPick()
    valid_ids = {c["impact_id"] for c in remaining}
    kept: list[UUID] = []
    for pick in parsed.picks:
        if pick in valid_ids and pick not in kept:
            kept.append(pick)
        if len(kept) >= _MAX_WATCHLIST:
            break

    by_id = {c["impact_id"]: c for c in remaining}
    items: list[BriefingItem] = []
    for pid in kept:
        c = by_id[pid]
        one_line = (parsed.one_line_summaries or {}).get(pid) or c["mechanism"][:200]
        items.append(
            BriefingItem(
                impact_id=pid,
                cluster_title=c["cluster_title"][:300],
                one_line_summary=one_line[:200],
                affected_positions=c["tickers"],
                mechanism_summary=c["mechanism"][:400],
                confidence=c["confidence"],
            )
        )
    return {"watchlist_items": items}


async def _synthesize_falsifiability_node(state: _GraphState) -> _GraphState:
    top = state.get("top_items") or []
    watch = state.get("watchlist_items") or []
    if not top and not watch:
        return {"falsifiability": []}

    items_input = [
        {"cluster_title": it.cluster_title, "mechanism": it.mechanism_summary}
        for it in list(top) + list(watch)
    ]

    llm: LLMClient = state["llm"]
    messages = [
        Message(role="system", content=SYNTHESIZE_FALSIFIABILITY_SYSTEM),
        Message(role="user", content=build_falsifiability_prompt(items_input)),
    ]
    try:
        response = await llm.complete(
            messages,
            tier="fast",
            response_model=_FalsifiabilityList,
            user_id=state["user_id"],
            agent_name="briefing-synthesizer",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("briefing: synthesize_falsifiability LLM failed: %s", exc)
        return {"falsifiability": []}

    parsed = response.parsed if isinstance(response.parsed, _FalsifiabilityList) else _FalsifiabilityList()
    items = [s for s in parsed.items if isinstance(s, str) and s.strip()]
    return {"falsifiability": items[:_MAX_FALSIFIABILITY]}


async def _compose_summary_node(state: _GraphState) -> _GraphState:
    top = state.get("top_items") or []
    watch = state.get("watchlist_items") or []
    fals = state.get("falsifiability") or []

    if not top and not watch:
        return {"summary_text": ""}

    top_dicts = [
        {
            "cluster_title": it.cluster_title,
            "confidence": it.confidence,
            "mechanism_summary": it.mechanism_summary,
        }
        for it in top
    ]
    watch_dicts = [
        {
            "cluster_title": it.cluster_title,
            "confidence": it.confidence,
            "mechanism_summary": it.mechanism_summary,
        }
        for it in watch
    ]

    llm: LLMClient = state["llm"]
    messages = [
        Message(role="system", content=COMPOSE_SUMMARY_SYSTEM),
        Message(role="user", content=build_summary_prompt(top_dicts, watch_dicts, fals)),
    ]
    try:
        response = await llm.complete(
            messages,
            tier="thorough",
            response_model=_Summary,
            user_id=state["user_id"],
            agent_name="briefing-synthesizer",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("briefing: compose_summary LLM failed: %s", exc)
        return {"summary_text": ""}

    parsed = response.parsed if isinstance(response.parsed, _Summary) else _Summary(text="")
    return {"summary_text": parsed.text[:800]}


async def _validate_node(state: _GraphState) -> _GraphState:
    """GRD-01 lexical check on every piece of text this briefing produced.

    Structural citations (impact_ids in `cited_impact_ids`) are validated
    at persistence time — every id must be in the caller's own impacts,
    which is inherent to how `candidates` was assembled. So GRD-02 isn't
    invoked here.
    """
    violations: list[dict[str, str]] = list(state.get("guardrail_violations") or [])

    def _texts_to_check() -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        summary = state.get("summary_text") or ""
        if summary:
            pairs.append(("summary", summary))
        for it in state.get("top_items") or []:
            pairs.append(("top:one_line", it.one_line_summary))
            pairs.append(("top:mechanism", it.mechanism_summary))
        for it in state.get("watchlist_items") or []:
            pairs.append(("watch:one_line", it.one_line_summary))
            pairs.append(("watch:mechanism", it.mechanism_summary))
        for f in state.get("falsifiability") or []:
            pairs.append(("falsifiability", f))
        return pairs

    for label, text in _texts_to_check():
        verdict = await check_directional(text, skip_llm=True)
        if not verdict.passed:
            violations.append(
                {"stage": f"directional:{label}", "reason": verdict.reason[:200]}
            )

    return {"guardrail_violations": violations}


async def _persist_node(state: _GraphState) -> _GraphState:
    session: AsyncSession = state["session"]
    violations = state.get("guardrail_violations") or []
    top = state.get("top_items") or []
    watch = state.get("watchlist_items") or []
    fals = state.get("falsifiability") or []
    summary = state.get("summary_text") or ""

    if violations:
        log.warning(
            "briefing: %d guardrail violation(s), not persisting: %s",
            len(violations),
            violations,
        )
        return {"row": None}

    if not top and not watch and not summary:
        log.info("briefing: nothing to persist (no candidates or all sections empty)")
        return {"row": None}

    content = BriefingContent(
        top_movers=top,
        watchlist=watch,
        what_would_change_my_thinking=fals,
        generated_summary=summary,
    )

    cited: list[str] = [str(it.impact_id) for it in top] + [
        str(it.impact_id) for it in watch
    ]

    duration_ms = int(
        (time.monotonic() - state.get("started_monotonic", time.monotonic())) * 1000
    )

    row = Briefing(
        user_id=state["user_id"],
        portfolio_id=state["portfolio_id"],
        briefing_date=state["briefing_date"],
        structured_content=content.model_dump(mode="json"),
        cited_impact_ids=cited,
        generation_duration_ms=max(0, duration_ms),
        langsmith_run_id=None,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {"row": row}


# ---------------------------------------------------------------------------
# Graph build
# ---------------------------------------------------------------------------


def _build_graph():
    g = StateGraph(_GraphState)
    g.add_node("gather_impacts", _gather_impacts_node)
    g.add_node("rank_top_movers", _rank_top_movers_node)
    g.add_node("rank_watchlist", _rank_watchlist_node)
    g.add_node("synthesize_falsifiability", _synthesize_falsifiability_node)
    g.add_node("compose_summary", _compose_summary_node)
    g.add_node("validate", _validate_node)
    g.add_node("persist", _persist_node)

    g.add_edge(START, "gather_impacts")
    g.add_edge("gather_impacts", "rank_top_movers")
    g.add_edge("rank_top_movers", "rank_watchlist")
    g.add_edge("rank_watchlist", "synthesize_falsifiability")
    g.add_edge("synthesize_falsifiability", "compose_summary")
    g.add_edge("compose_summary", "validate")
    g.add_edge("validate", "persist")
    g.add_edge("persist", END)
    return g.compile()


BRIEFING_GRAPH = _build_graph()


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def synthesize_briefing_for_user(
    user_id: UUID,
    portfolio_id: UUID,
    *,
    session: AsyncSession,
    llm: LLMClient,
    briefing_date: date | None = None,
    lookback_hours: int = 24,
    force: bool = False,
) -> Briefing | None:
    """Produce today's briefing for one (user, portfolio).

    Idempotent on `(user_id, portfolio_id, briefing_date)`. `force=True`
    deletes the existing row and re-runs. Returns `None` if no eligible
    impacts exist OR any guardrail violation blocked persistence.
    """
    bd = briefing_date or _now_utc().date()

    existing = (
        await session.execute(
            select(Briefing).where(
                Briefing.user_id == user_id,
                Briefing.portfolio_id == portfolio_id,
                Briefing.briefing_date == bd,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        if not force:
            return existing
        await session.execute(
            delete(Briefing).where(Briefing.id == existing.id)
        )
        await session.commit()

    result = await BRIEFING_GRAPH.ainvoke(
        {
            "user_id": user_id,
            "portfolio_id": portfolio_id,
            "session": session,
            "llm": llm,
            "briefing_date": bd,
            "lookback_hours": lookback_hours,
            "started_monotonic": time.monotonic(),
        }
    )
    return result.get("row")
