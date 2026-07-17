"""GRD-03: out-of-scope refusal classifier.

Lumen's PRD (Section 5) draws a hard boundary around regulated advice: no
tax, no legal, no personal financial planning, no medical guidance. This
module is the input-side guardrail — every user chat message runs through
`classify_scope` before it reaches the answer path. If the message asks
for regulated advice, the caller returns a canned refusal pointing the
user at a licensed professional instead of a Lumen answer.

The classifier is two-stage on purpose:

1. **Lexical screen** — a curated set of high-precision keyword and phrase
   patterns per category. Fast, deterministic, no LLM call. Meant to catch
   the obvious out-of-scope asks (e.g., "capital gains tax", "should I
   buy a house") without spending a token.
2. **LLM fallback** — only invoked when the lexical screen is clean and
   `skip_llm=False`. Uses the fast tier and structured JSON output to
   catch subtler phrasings the keyword list misses.

The lexical stage is intentionally biased toward false positives — a
mistaken refusal is user-visible but recoverable; a missed regulated
question is not. Callers that only want the cheap screen can pass
`skip_llm=True`.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.utils.llm import LLMClient, Message

log = logging.getLogger(__name__)


Category = Literal["in_scope", "tax", "legal", "personal_planning", "medical"]

_OUT_OF_SCOPE_CATEGORIES: tuple[Category, ...] = (
    "tax",
    "legal",
    "personal_planning",
    "medical",
)

# Cap the text we scan/send. Chat inputs are usually short; pathological
# multi-thousand-char pastes get trimmed so the LLM call stays fast and the
# regex sweep bounded.
_MAX_SCAN_CHARS = 4000


@dataclass
class ScopeVerdict:
    category: Category
    passed: bool
    refusal_message: str


class _ScopeCheck(BaseModel):
    """Structured output from the LLM fallback."""

    category: Category
    rationale: str = Field(default="", max_length=200)


_REFUSAL_MESSAGES: dict[Category, str] = {
    "in_scope": "",
    "tax": (
        "Lumen doesn't give tax advice — that's regulated territory. A licensed "
        "CPA or enrolled agent (find one via https://taxpayeradvocate.irs.gov/) "
        "can help with your specific situation."
    ),
    "legal": (
        "Lumen doesn't give legal advice. A licensed attorney (find one via "
        "your local bar association) can review your specific circumstances."
    ),
    "personal_planning": (
        "Lumen focuses on how news mechanically affects positions you hold — "
        "not personal financial planning (buying homes, budgeting, retirement "
        "timing). A fee-only CFP® (https://letsmakeaplan.org/) can help you "
        "build a plan."
    ),
    "medical": (
        "Lumen doesn't give medical advice. Please consult a licensed physician "
        "or the appropriate professional for medical questions."
    ),
}


# Pattern kinds:
#   "phrase" — case-insensitive substring, used for multi-word triggers where
#             word-boundary regexes are awkward (hyphens, common function
#             words in the middle).
#   "word"   — \b<word>\b, case-insensitive; avoids "sue" matching "issue".
#   "prefix" — \b<prefix>\w*, so "diagnos" catches diagnose/diagnosis/diagnosed.
#
# Ordered most-specific → least-specific within each category so a debug log
# of the winning pattern surfaces the most informative match first.
_PATTERNS: dict[Category, list[tuple[str, str]]] = {
    "tax": [
        ("phrase", "tax-loss harvest"),
        ("phrase", "capital gains tax"),
        ("phrase", "cost basis for taxes"),
        ("phrase", "hsa contribution"),
        ("phrase", "roth conversion"),
        ("phrase", "tax bracket"),
        ("phrase", "should i file"),
        ("word", "1099"),
        ("word", "irs"),
        ("word", "audit"),
    ],
    "legal": [
        ("phrase", "power of attorney"),
        ("phrase", "estate plan"),
        ("word", "lawsuit"),
        ("word", "attorney"),
        ("word", "prenup"),
        ("word", "sue"),
        ("word", "will"),
    ],
    "personal_planning": [
        ("phrase", "should i buy a house"),
        ("phrase", "how much should i save"),
        ("phrase", "when can i retire"),
        ("phrase", "afford a car"),
        ("phrase", "emergency fund"),
        ("phrase", "budget for"),
    ],
    "medical": [
        ("phrase", "side effect"),
        ("prefix", "diagnos"),
        ("word", "prescription"),
        ("word", "medication"),
        ("word", "doctor"),
        ("word", "symptom"),
    ],
}


def _compile(kind: str, phrase: str) -> re.Pattern[str]:
    if kind == "phrase":
        return re.compile(re.escape(phrase), re.IGNORECASE)
    if kind == "prefix":
        return re.compile(rf"\b{re.escape(phrase)}\w*", re.IGNORECASE)
    return re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)


_COMPILED_PATTERNS: dict[Category, list[re.Pattern[str]]] = {
    cat: [_compile(kind, phrase) for kind, phrase in patterns]
    for cat, patterns in _PATTERNS.items()
}


def _lexical_screen(text: str) -> Category | None:
    """First-hit wins across categories in `_OUT_OF_SCOPE_CATEGORIES` order."""
    for category in _OUT_OF_SCOPE_CATEGORIES:
        for pattern in _COMPILED_PATTERNS[category]:
            if pattern.search(text):
                return category
    return None


_LLM_SYSTEM_PROMPT = (
    "You are Lumen's out-of-scope classifier. Lumen is a financial-intelligence "
    "assistant that answers questions about market news, macro events, how "
    "those events mechanically affect portfolio positions, cited assessments, "
    "and the history or transmission mechanism of an event. Anything else is "
    "out of scope.\n\n"
    "Classify the user's message into EXACTLY ONE of:\n"
    "  - `in_scope`: news, markets, portfolio impact, cited assessments, "
    "history/mechanism explanations.\n"
    "  - `tax`: tax filing, tax planning, tax-loss harvesting, capital-gains "
    "tax, IRS questions, retirement-account tax mechanics.\n"
    "  - `legal`: lawsuits, wills, prenups, estate planning, attorneys, "
    "contracts, personal legal advice.\n"
    "  - `personal_planning`: budgeting, buying homes, affording purchases, "
    "saving rates, retirement timing — anything about the user's personal "
    "financial plan rather than the market.\n"
    "  - `medical`: symptoms, medications, diagnoses, side effects, doctors.\n\n"
    "Reply with a JSON object containing `category` (one of the five labels "
    "exactly) and `rationale` (a single short line, ≤200 chars)."
)


async def classify_scope(
    text: str,
    *,
    llm: LLMClient | None = None,
    skip_llm: bool = False,
) -> ScopeVerdict:
    """Classify `text` as `in_scope` or one of four regulated-advice buckets.

    Order of operations:

    1. Trim and cap the input.
    2. Run the lexical screen; a hit short-circuits and returns the canned
       refusal without an LLM call.
    3. If lexical is clean and `skip_llm=True`, return `in_scope`.
    4. Otherwise call the LLM (fast tier, structured output). LLM failures
       fall back to `in_scope` — the guardrail is fail-open on infrastructure
       errors because a spurious refusal is worse than a rare miss the
       downstream disclaimer already covers.
    """
    text = (text or "").strip()
    if not text:
        return ScopeVerdict(category="in_scope", passed=True, refusal_message="")

    scan_text = text[:_MAX_SCAN_CHARS]

    hit = _lexical_screen(scan_text)
    if hit is not None:
        return ScopeVerdict(
            category=hit,
            passed=False,
            refusal_message=_REFUSAL_MESSAGES[hit],
        )

    if skip_llm or llm is None:
        return ScopeVerdict(category="in_scope", passed=True, refusal_message="")

    try:
        response = await llm.complete(
            [
                Message(role="system", content=_LLM_SYSTEM_PROMPT),
                Message(role="user", content=scan_text),
            ],
            tier="fast",
            response_model=_ScopeCheck,
            agent_name="guardrail-scope",
        )
    except Exception:
        log.exception("scope guardrail LLM call failed; defaulting to in_scope")
        return ScopeVerdict(category="in_scope", passed=True, refusal_message="")

    parsed = response.parsed
    if not isinstance(parsed, _ScopeCheck):
        # Structured-output enforcement should mean this is unreachable, but be
        # defensive: an unexpected shape shouldn't crash the request.
        log.warning("scope guardrail: LLM returned unexpected shape, defaulting to in_scope")
        return ScopeVerdict(category="in_scope", passed=True, refusal_message="")

    category = parsed.category
    if category == "in_scope":
        return ScopeVerdict(category="in_scope", passed=True, refusal_message="")

    return ScopeVerdict(
        category=category,
        passed=False,
        refusal_message=_REFUSAL_MESSAGES[category],
    )
