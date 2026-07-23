"""Prompt builders and system-prompt constants for the chat agent (CHAT-03).

Three system prompts — one per LLM-touching node in the graph — and one user-
prompt builder used by `compose_response`.

The composed user prompt renders the original user message plus a compact,
structured dump of whatever tools we ran. The `compose_response` LLM is
strictly instructed to answer using only that context.
"""
from __future__ import annotations

from typing import Any


INTENT_SYSTEM = (
    "You classify the user's chat message into one of: portfolio-context, "
    "news-question, mechanism-question. Reply with the label and a short "
    "rationale."
)

ROUTE_TOOLS_SYSTEM = (
    "You decide which retrieval tools to call. Options: portfolio_summary, "
    "recent_impacts, news. Return a plan."
)

COMPOSE_SYSTEM = (
    "You are Lumen's chat agent. Answer using ONLY the provided context. "
    "Cite every non-trivial claim. No directional language — never buy/sell/"
    "add/trim/consider/should. Describe mechanism."
)


_MAX_SNIPPET_CHARS = 500
_MAX_IMPACT_MECHANISM_CHARS = 400


def _render_portfolio(summary: Any) -> str:
    if summary is None:
        return "  (portfolio_summary not requested or unavailable)"
    lines = [
        f"name: {summary.portfolio_name}",
        f"portfolio_id: {summary.portfolio_id}",
    ]
    if summary.positions:
        pos_render = ", ".join(
            f"{p.get('ticker')}({p.get('asset_type', 'equity')})"
            for p in summary.positions
        )
        lines.append(f"positions: {pos_render}")
    else:
        lines.append("positions: (none)")
    if summary.themes:
        themes = ", ".join(
            f"{t.get('description')} (w={t.get('weight')})"
            for t in summary.themes
        )
        lines.append(f"themes: {themes}")
    if summary.latest_briefing_summary:
        lines.append(
            f"latest_briefing ({summary.latest_briefing_date}): "
            f"{summary.latest_briefing_summary[:400]}"
        )
    return "\n".join(f"- {line}" for line in lines)


def _render_impacts(impacts: list[Any]) -> str:
    if not impacts:
        return "  (recent_impacts not requested or empty)"
    lines: list[str] = []
    for imp in impacts:
        mechanism = (imp.mechanism or "")[:_MAX_IMPACT_MECHANISM_CHARS]
        confidence = getattr(imp, "confidence", None)
        conf_str = f"{float(confidence):.2f}" if confidence is not None else "?"
        lines.append(
            f"- cluster_id={imp.cluster_id} confidence={conf_str} "
            f"mechanism={mechanism}"
        )
    return "\n".join(lines)


def _render_news(snippets: list[Any]) -> str:
    if not snippets:
        return "  (news not requested or empty)"
    lines: list[str] = []
    for s in snippets:
        body = (s.snippet or "").replace("\n", " ")[:_MAX_SNIPPET_CHARS]
        lines.append(
            f"- source={s.source} url={s.url} title={s.title!r} "
            f"published={s.published_at.isoformat() if s.published_at else '?'} "
            f"similarity={s.similarity:.2f}\n  body: {body}"
        )
    return "\n".join(lines)


def build_compose_prompt(state: dict[str, Any]) -> str:
    """Compose the user prompt for the thorough-tier response LLM.

    Includes the raw user question plus a structured dump of tool results. The
    LLM's system prompt already forbids directional language and mandates that
    every non-trivial claim carry a citation.
    """
    user_message = (state.get("user_message") or "").strip()
    return (
        "User question:\n"
        f"{user_message}\n\n"
        "Portfolio context:\n"
        f"{_render_portfolio(state.get('portfolio_summary'))}\n\n"
        "Recent impact assessments:\n"
        f"{_render_impacts(state.get('recent_impacts') or [])}\n\n"
        "News snippets (only these URLs may be cited):\n"
        f"{_render_news(state.get('news_snippets') or [])}\n\n"
        "Rules:\n"
        "- Answer the user's question using ONLY the context above.\n"
        "- If citing a news snippet, `citations[].url` MUST match one of the "
        "URLs listed above and `citations[].quote` MUST be a verbatim substring "
        "of that snippet's body.\n"
        "- Describe mechanism, not action. Do NOT tell the reader to buy/sell/"
        "add/trim/hold, or use words like `should`, `consider`, `recommend`.\n"
        "- Keep `content` under 4000 characters."
    )
