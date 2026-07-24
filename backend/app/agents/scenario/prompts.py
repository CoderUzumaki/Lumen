"""Prompt builders for the scenario simulator graph (SIM-02).

Mirrors `app/agents/impact/prompts.py`'s shape — a shared ``SCENARIO_SYSTEM``
and one user-message builder ``build_reason_prompt``. Unlike IMP-04, there
is no repair prompt: SIM-02 is a single-attempt graph (see the module
docstring in ``graph.py`` for the rationale).
"""
from __future__ import annotations

import json
from typing import Any

from app.schemas.scenario import ScenarioSimulation

SCENARIO_SYSTEM = (
    "You are Lumen's scenario analyst. Given a hypothetical scenario, "
    "the reader's portfolio, historical analogs, and recent price context, "
    "produce a structured impact assessment across each position. "
    "Use mechanism language only — never buy/sell/add/trim/consider/should. "
    "Be honest about uncertainty. State your key assumptions and one "
    "falsifiability criterion."
)

# Re-stated in-prompt so the model doesn't need to be told twice; GRD-01
# also rejects these lexically.
_FORBIDDEN_PHRASES: tuple[str, ...] = (
    "buy", "sell", "add", "trim", "overweight", "underweight",
    "consider", "should",
)


def _render_positions(positions: list[Any]) -> str:
    if not positions:
        return "  (no positions in this portfolio)"
    lines: list[str] = []
    for p in positions:
        asset_type = getattr(p, "asset_type", None) or "equity"
        exch = f" exchange={p.exchange}" if getattr(p, "exchange", None) else ""
        lines.append(
            f"- id={p.id} ticker={p.ticker} asset_type={asset_type}{exch}"
        )
    return "\n".join(lines)


def _render_themes(themes: list[Any]) -> str:
    if not themes:
        return "  (no user themes)"
    lines: list[str] = []
    for t in themes:
        weight = getattr(t, "weight", None)
        weight_str = f" weight={weight}" if weight is not None else ""
        lines.append(f"- {t.description}{weight_str}")
    return "\n".join(lines)


def _render_analogs(analogs: list[Any]) -> str:
    if not analogs:
        return "  (no historical analogs retrieved)"
    lines: list[str] = []
    for a in analogs:
        lines.append(
            f"- {a.event_description} | {a.when.isoformat()} | "
            f"{a.outcome_description} (similarity={a.similarity_score:.2f})"
        )
    return "\n".join(lines)


def _render_prices(price_contexts: dict[str, Any]) -> str:
    if not price_contexts:
        return "  (no ticker price context available)"
    lines: list[str] = []
    for ticker, ctx in price_contexts.items():
        if ctx is None:
            lines.append(f"- {ticker}: price unavailable")
            continue
        lines.append(
            f"- {ticker}: pct_1d={ctx.pct_change_1d:+.3f} "
            f"pct_5d={ctx.pct_change_5d:+.3f} "
            f"pct_30d={ctx.pct_change_30d:+.3f} "
            f"pct_ytd={ctx.pct_change_ytd:+.3f} "
            f"currency={ctx.currency}"
        )
    return "\n".join(lines)


def _schema_str() -> str:
    return json.dumps(ScenarioSimulation.model_json_schema())


def _forbidden_line() -> str:
    return (
        "- Do NOT include phrases like "
        + ", ".join(f'"{p}"' for p in _FORBIDDEN_PHRASES)
        + ". Describe mechanics only."
    )


def build_reason_prompt(state: dict[str, Any]) -> str:
    """User message for the `reason_scenario` LLM call.

    Slots in the scenario text, a compact portfolio+themes summary, the
    retrieved analogs, per-ticker price context, and the `ScenarioSimulation`
    JSON schema.
    """
    scenario_text: str = state.get("scenario_text") or ""
    positions = state.get("positions") or []
    themes = state.get("themes") or []
    analogs = state.get("analogs") or []
    price_contexts = state.get("price_contexts") or {}

    return (
        "Scenario:\n"
        f"{scenario_text}\n\n"
        "Portfolio positions:\n"
        f"{_render_positions(positions)}\n\n"
        "User themes:\n"
        f"{_render_themes(themes)}\n\n"
        "Historical analogs (from retrieval):\n"
        f"{_render_analogs(analogs)}\n\n"
        "Recent price context:\n"
        f"{_render_prices(price_contexts)}\n\n"
        "Output a JSON object matching this schema:\n"
        f"{_schema_str()}\n\n"
        "Rules:\n"
        "- `scenario_text` must echo the scenario exactly as supplied.\n"
        "- `per_position_impact` should contain one entry per portfolio "
        "position that the scenario touches; each `mechanism` must describe "
        "the transmission channel in cause-effect terms.\n"
        "- `portfolio_summary` should aggregate the per-position impacts into "
        "one paragraph about the portfolio as a whole.\n"
        "- `key_assumptions` names the working assumptions your analysis "
        "leans on (max 10).\n"
        "- `falsifiability` must name a specific observable that would flip "
        "your read.\n"
        "- `citations` may be empty for a scenario — the historical analogs "
        "are the grounding.\n"
        f"{_forbidden_line()}"
    )
