"""Prompt templates for the briefing synthesizer (BRIEF-02).

Four LLM stages, each with its own system+user prompt pair:

1. `rank_top_movers` — fast tier — pick 3–5 impact UUIDs.
2. `rank_watchlist` — fast tier — pick 3–5 developing situations from the
   remaining candidates.
3. `synthesize_falsifiability` — fast tier — extract 3–5 observable pivot
   events across the day's top movers + watchlist.
4. `compose_generated_summary` — thorough tier — a ≤100-word overview.

Every prompt enforces PRD principle #2: no directional language. The
GRD-01 guardrail runs downstream regardless.
"""
from __future__ import annotations

from typing import Any, Iterable


_NO_ACTION_RULE = (
    "Use mechanism language only. Never say buy, sell, add, trim, "
    "overweight, underweight, consider, or should. Describe what the news "
    "mechanically means; do not tell the reader what to do."
)


RANK_TOP_MOVERS_SYSTEM = (
    "You are Lumen's briefing curator. From the candidate impact assessments, "
    "pick the 3–5 that are most consequential for the reader's portfolio "
    "today. Rank by potential magnitude × confidence. "
    + _NO_ACTION_RULE
)

RANK_WATCHLIST_SYSTEM = (
    "You are Lumen's briefing curator. From the impact assessments that did "
    "NOT make the top movers, pick 3–5 developing situations worth watching. "
    + _NO_ACTION_RULE
)

SYNTHESIZE_FALSIFIABILITY_SYSTEM = (
    "You are Lumen's briefing curator. From these impact assessments, extract "
    "3–5 specific observable events that would flip the current read "
    "(positive → negative or vice versa). Each item is one sentence, "
    "mechanism-focused. " + _NO_ACTION_RULE
)

COMPOSE_SUMMARY_SYSTEM = (
    "You are Lumen's briefing writer. In roughly 100 words (max 800 characters), "
    "summarize what today's news mechanically means for the reader's portfolio. "
    "Highlight the transmission channels — rates, earnings, geopolitics, "
    "sector rotations — with honest uncertainty. " + _NO_ACTION_RULE
)


def _format_candidate_line(candidate: dict[str, Any]) -> str:
    """Compact per-candidate line for ranking prompts."""
    return (
        f"- id={candidate['impact_id']} "
        f"cluster={candidate['cluster_title']!r} "
        f"confidence={candidate['confidence']:.2f} "
        f"tickers={','.join(candidate.get('tickers') or []) or 'none'} "
        f"mechanism={candidate['mechanism'][:200]!r}"
    )


def build_rank_prompt(
    candidates: Iterable[dict[str, Any]], *, purpose: str = "top_movers"
) -> str:
    lines = [_format_candidate_line(c) for c in candidates]
    header = "Top-movers candidates:" if purpose == "top_movers" else "Watchlist candidates:"
    if not lines:
        return f"{header}\n(none available)"
    return f"{header}\n" + "\n".join(lines) + (
        "\n\nReturn a JSON object with `picks: list[UUID]` (3–5 items) and "
        "`one_line_summaries: dict[UUID, str]` mapping each pick to a "
        "≤200-char summary of its mechanism."
    )


def build_falsifiability_prompt(items: Iterable[dict[str, Any]]) -> str:
    lines = [
        f"- {i['cluster_title']}: {i['mechanism'][:300]}"
        for i in items
    ]
    if not lines:
        return "No items available. Return an empty list."
    return (
        "Impact assessments in today's briefing:\n"
        + "\n".join(lines)
        + "\n\nReturn a JSON object with `items: list[str]` (3–5 short "
        "falsifiability sentences, each ≤200 chars)."
    )


def build_summary_prompt(
    top_movers: Iterable[dict[str, Any]],
    watchlist: Iterable[dict[str, Any]],
    falsifiability: Iterable[str],
) -> str:
    def _block(label: str, rows: Iterable[dict[str, Any]]) -> str:
        rows = list(rows)
        if not rows:
            return f"{label}: (none)"
        lines = [
            f"  - {r['cluster_title']} (conf={r['confidence']:.2f}): {r['mechanism_summary']}"
            for r in rows
        ]
        return f"{label}:\n" + "\n".join(lines)

    fals = list(falsifiability)
    fals_block = (
        "Falsifiability:\n" + "\n".join(f"  - {f}" for f in fals)
        if fals
        else "Falsifiability: (none)"
    )

    return "\n\n".join(
        [
            _block("Top movers", top_movers),
            _block("Watchlist", watchlist),
            fals_block,
            "Return a JSON object with `text: str` (≤800 chars). "
            "Do NOT recommend action.",
        ]
    )
