"""GRD-01: Directional-language guardrail.

Impact analyst drafts sometimes slip into action recommendations ("buy TLT",
"trim NVDA", "you should"). PRD principle #2: no directional language — only
mechanism, magnitude, falsifiability. This module runs a cheap lexical check
first, then (if lexical passes) asks a fast-tier LLM whether the draft still
recommends a specific action to the reader.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.utils.llm import LLMClient, Message


_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "buy", "sell", "hold", "add", "trim", "overweight", "underweight",
    "long", "short", "bullish", "bearish", "consider", "should",
    "recommend", "advise",
)

_TOKEN_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _FORBIDDEN_TOKENS) + r")\b",
    re.IGNORECASE,
)


@dataclass
class DirectionalVerdict:
    passed: bool
    reason: str  # <= 200 chars; empty when passed=True
    matched_tokens: list[str]  # lexical hits (may be non-empty even when LLM overrides)
    llm_asked: bool  # True if the LLM stage ran


def lexical_check(text: str) -> list[str]:
    """Return the deduplicated, alphabetically sorted forbidden tokens in `text`.

    Word-boundary, case-insensitive. `long`/`short` are legitimate financial
    nouns elsewhere ("long-duration bonds") — flagged anyway per BUILD.md.
    """
    hits = {m.group(1).lower() for m in _TOKEN_RE.finditer(text)}
    return sorted(hits)


class _DirectionalCheck(BaseModel):
    """Structured output for the LLM YES/NO stage."""

    recommends_action: bool
    rationale: str = Field(max_length=200)


_SYSTEM_PROMPT = (
    "You are a strict guardrail. Answer YES or NO. YES only when the text "
    "tells the reader to take a specific investment action (buy/sell/add/"
    "trim/increase-position/decrease-position). Mechanism language (rates "
    "cause valuation compression) is NOT a recommendation. Return a JSON "
    "object with `recommends_action` (bool) and `rationale` (<=200 chars)."
)


def _truncate(text: str, limit: int = 200) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def check_directional(
    text: str,
    *,
    llm: LLMClient | None = None,
    skip_llm: bool = False,
) -> DirectionalVerdict:
    """Two-stage directional guardrail: lexical, then optional fast-tier LLM.

    - Lexical hit → immediate reject with ``matched_tokens`` populated;
      the LLM is NOT invoked and ``llm_asked=False``.
    - Lexical clean → if ``skip_llm`` (or ``llm is None``), accept.
      Otherwise ask a fast-tier LLM whether the draft tells the reader to
      take a specific action; reject on YES.
    """
    hits = lexical_check(text)
    if hits:
        return DirectionalVerdict(
            passed=False,
            reason=_truncate(f"forbidden directional tokens: {', '.join(hits)}"),
            matched_tokens=hits,
            llm_asked=False,
        )

    if skip_llm or llm is None:
        return DirectionalVerdict(
            passed=True, reason="", matched_tokens=[], llm_asked=False
        )

    response = await llm.complete(
        [
            Message(role="system", content=_SYSTEM_PROMPT),
            Message(
                role="user",
                content=(
                    "Draft:\n"
                    f"{text}\n\n"
                    "Does this recommend a specific action to the reader?"
                ),
            ),
        ],
        tier="fast",
        response_model=_DirectionalCheck,
        agent_name="guardrail-directional",
    )
    parsed: _DirectionalCheck = response.parsed  # type: ignore[assignment]
    if parsed.recommends_action:
        return DirectionalVerdict(
            passed=False,
            reason=_truncate(f"LLM flagged recommendation: {parsed.rationale}"),
            matched_tokens=[],
            llm_asked=True,
        )
    return DirectionalVerdict(
        passed=True, reason="", matched_tokens=[], llm_asked=True
    )
