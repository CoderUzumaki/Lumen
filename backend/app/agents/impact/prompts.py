"""Prompt builders for the impact-analyst graph (IMP-04).

Two builders — one for the first attempt (`build_reason_prompt`) and one for
the guardrail-repair retry (`build_repair_prompt`). Both compose a user
message from the graph state; the shared system prompt lives in `SYSTEM_PROMPT`.

The prompt body is verbatim from BUILD.md IMP-04 — the language ("mechanism
only", "never recommend action", "cite sources") is deliberate and the
guardrail suite (GRD-01 / GRD-02) will re-check the LLM's output regardless,
so keep the surface language stable across edits.
"""
from __future__ import annotations

import json
from typing import Any

from app.schemas.impact import ImpactAssessment as ImpactAssessmentPayload

SYSTEM_PROMPT = (
    "You are Lumen's impact analyst. You analyze how a news event mechanically "
    "transmits to specific portfolio positions. You never recommend action. "
    "You always cite sources."
)

_BODY_MAX_CHARS = 2000

# BUILD.md IMP-04 forbids these tokens outright; GRD-01 also blocks them
# lexically. Repeat them in-prompt so the model does not have to be told twice.
_FORBIDDEN_PHRASES: tuple[str, ...] = (
    "buy", "sell", "add", "trim", "overweight", "underweight",
    "consider", "should",
)


def _render_citation_stubs(stubs: list[Any]) -> str:
    if not stubs:
        return "  (no sources supplied — you MUST NOT invent citations)"
    lines: list[str] = []
    for stub in stubs:
        body = (stub.body or "").strip().replace("\n", " ")
        if len(body) > 400:
            body = body[:397] + "..."
        lines.append(f"- url: {stub.url}\n  body: {body}")
    return "\n".join(lines)


def _render_positions(positions: list[Any]) -> str:
    if not positions:
        return "  (no positions surfaced by the relevance engine)"
    lines: list[str] = []
    for p in positions:
        asset_type = getattr(p, "asset_type", None) or "equity"
        exch = f" exchange={p.exchange}" if getattr(p, "exchange", None) else ""
        lines.append(
            f"- id={p.id} ticker={p.ticker} asset_type={asset_type}{exch}"
        )
    return "\n".join(lines)


def _render_analogs(analogs: list[Any]) -> str:
    if not analogs:
        return "  (no historical analogs retrieved)"
    lines: list[str] = []
    for a in analogs:
        lines.append(
            f"- {a.event_description} | {a.when.isoformat()} | {a.outcome_description}"
            f" (similarity={a.similarity_score:.2f})"
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
    return json.dumps(ImpactAssessmentPayload.model_json_schema())


def _forbidden_line() -> str:
    return (
        "- Do NOT include phrases like "
        + ", ".join(f'"{p}"' for p in _FORBIDDEN_PHRASES)
        + ". Describe mechanics only."
    )


def build_reason_prompt(state: dict[str, Any]) -> str:
    """User message for the initial `reason_mechanism` LLM call.

    Verbatim from BUILD.md IMP-04 — slots in cluster title, first
    2000 chars of body, citation stubs (url + body), touched position
    list, retrieved analogs, price context, and the `ImpactAssessment`
    JSON schema.
    """
    cluster = state["cluster"]
    news_items = state.get("news_items") or []
    body_source = news_items[0].body if news_items and news_items[0].body else ""
    body = body_source[:_BODY_MAX_CHARS]

    return (
        "Event cluster:\n"
        f"Title: {cluster.canonical_title}\n"
        f"Body: {body}\n"
        "Sources:\n"
        f"{_render_citation_stubs(state.get('source_stubs') or [])}\n\n"
        "User's touched positions (from relevance engine):\n"
        f"{_render_positions(state.get('positions') or [])}\n\n"
        "Historical analogs (from retrieval):\n"
        f"{_render_analogs(state.get('analogs') or [])}\n\n"
        "Recent price context:\n"
        f"{_render_prices(state.get('price_contexts') or {})}\n\n"
        "Output a JSON object matching this schema:\n"
        f"{_schema_str()}\n\n"
        "Rules:\n"
        "- The `mechanism` field must describe the transmission channel in cause-effect terms.\n"
        "- The `magnitude_low` and `magnitude_high` fields are honest ranges (nullable if unknowable).\n"
        "- `falsifiability` must name a specific observable that would flip your read.\n"
        "- `citations` must reference the news sources you drew from — only URLs listed above.\n"
        f"{_forbidden_line()}"
    )


def build_repair_prompt(state: dict[str, Any]) -> str:
    """User message for the guardrail-repair retry.

    Lists each guardrail violation verbatim and asks the LLM to produce a
    corrected draft. Preserves the original event/sources/positions context
    and re-attaches the schema so the response shape does not drift.
    """
    violations = state.get("guardrail_violations") or []
    if violations:
        lines = "\n".join(
            f"- [{v.get('stage', 'unknown')}] {v.get('reason', '')}"
            for v in violations
        )
    else:
        lines = "  (no violations recorded — repair still requested)"

    return (
        "Your previous draft failed one or more guardrails:\n"
        f"{lines}\n\n"
        "Produce a corrected `ImpactAssessment` that fixes every violation above. "
        "The context below is unchanged from the previous turn — do not invent "
        "new sources or positions.\n\n"
        + build_reason_prompt(state)
    )
