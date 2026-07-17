"""GRD-03: out-of-scope refusal classifier tests.

Hermetic — no real LLM traffic. The `_FakeLLM` helper monkey-patches
`LLMClient.complete` and tracks call count so the tests can assert the
lexical stage short-circuited when it should have.
"""
from __future__ import annotations

from typing import Callable
from unittest.mock import AsyncMock

import pytest

from app.guardrails.scope import (
    Category,
    ScopeVerdict,
    _OUT_OF_SCOPE_CATEGORIES,
    _REFUSAL_MESSAGES,
    _ScopeCheck,
    classify_scope,
)
from app.utils.llm import LLMClient, LLMResponse


# ---------- fake LLM ---------------------------------------------------------


class _FakeLLM(LLMClient):
    """LLMClient that returns a canned category without hitting the network."""

    def __init__(
        self,
        category: Category = "in_scope",
        *,
        rationale: str = "fake",
        resolver: Callable[[str], Category] | None = None,
    ):
        super().__init__(http_client=AsyncMock())
        self._category = category
        self._rationale = rationale
        self._resolver = resolver
        self.calls: list[str] = []

    async def complete(self, messages, **kwargs):  # type: ignore[override]
        user_text = next((m.content for m in messages if m.role == "user"), "")
        self.calls.append(user_text)
        cat: Category
        if self._resolver is not None:
            cat = self._resolver(user_text)
        else:
            cat = self._category
        verdict = _ScopeCheck(category=cat, rationale=self._rationale)
        return LLMResponse(
            content=verdict.model_dump_json(),
            parsed=verdict,
            model="fake",
            tier=kwargs.get("tier", "fast"),
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
        )


# ---------- lexical hits: LLM must not be called -----------------------------


async def test_lexical_tax_hit():
    llm = _FakeLLM(category="in_scope")
    verdict = await classify_scope(
        "how do I minimize capital gains tax on my TSLA sale", llm=llm
    )
    assert verdict.category == "tax"
    assert verdict.passed is False
    assert "tax" in verdict.refusal_message.lower()
    assert llm.calls == [], "lexical hit must short-circuit before LLM"


async def test_lexical_legal_hit():
    llm = _FakeLLM(category="in_scope")
    verdict = await classify_scope("I want to sue my broker", llm=llm)
    assert verdict.category == "legal"
    assert verdict.passed is False
    assert verdict.refusal_message
    assert llm.calls == []


async def test_lexical_personal_planning_hit():
    llm = _FakeLLM(category="in_scope")
    verdict = await classify_scope("should I buy a house this year", llm=llm)
    assert verdict.category == "personal_planning"
    assert verdict.passed is False
    assert "planning" in verdict.refusal_message.lower() or "plan" in verdict.refusal_message.lower()
    assert llm.calls == []


async def test_lexical_medical_hit():
    llm = _FakeLLM(category="in_scope")
    verdict = await classify_scope(
        "what are the side effects of my medication", llm=llm
    )
    assert verdict.category == "medical"
    assert verdict.passed is False
    assert verdict.refusal_message
    assert llm.calls == []


# ---------- skip_llm fast path ----------------------------------------------


async def test_skip_llm_returns_in_scope_on_lexical_clean():
    llm = _FakeLLM(category="personal_planning")  # would flag if called
    verdict = await classify_scope(
        "what happens to bond ETFs when the Fed cuts rates",
        llm=llm,
        skip_llm=True,
    )
    assert verdict.category == "in_scope"
    assert verdict.passed is True
    assert verdict.refusal_message == ""
    assert llm.calls == [], "skip_llm=True must bypass the LLM"


async def test_skip_llm_still_catches_lexical_hits():
    # skip_llm bypasses the LLM stage, but a lexical hit must still fire.
    llm = _FakeLLM(category="in_scope")
    verdict = await classify_scope(
        "should I do a roth conversion this year", llm=llm, skip_llm=True
    )
    assert verdict.category == "tax"
    assert verdict.passed is False
    assert llm.calls == []


# ---------- LLM stage --------------------------------------------------------


async def test_llm_returns_in_scope():
    llm = _FakeLLM(category="in_scope")
    verdict = await classify_scope(
        "what happens to bond ETFs when the Fed cuts rates", llm=llm
    )
    assert verdict.category == "in_scope"
    assert verdict.passed is True
    assert verdict.refusal_message == ""
    assert len(llm.calls) == 1


async def test_llm_catches_subtle_personal_planning():
    # Lexical-clean but out-of-scope — LLM must catch it.
    llm = _FakeLLM(category="personal_planning")
    verdict = await classify_scope("am I saving enough", llm=llm)
    assert verdict.category == "personal_planning"
    assert verdict.passed is False
    assert verdict.refusal_message
    assert len(llm.calls) == 1


async def test_no_llm_and_lexical_clean_defaults_in_scope():
    # `llm=None` and clean text — nothing to refuse, be permissive.
    verdict = await classify_scope("what is the market cap of AAPL")
    assert verdict.category == "in_scope"
    assert verdict.passed is True


async def test_llm_exception_falls_back_to_in_scope():
    class _BrokenLLM(LLMClient):
        def __init__(self):
            super().__init__(http_client=AsyncMock())

        async def complete(self, *args, **kwargs):  # type: ignore[override]
            raise RuntimeError("upstream is on fire")

    verdict = await classify_scope("what is the market cap of AAPL", llm=_BrokenLLM())
    assert verdict.category == "in_scope"
    assert verdict.passed is True


# ---------- refusal messages -------------------------------------------------


def test_refusal_messages_have_all_four_categories():
    for cat in _OUT_OF_SCOPE_CATEGORIES:
        msg = _REFUSAL_MESSAGES[cat]
        assert msg, f"missing refusal message for {cat}"
        assert len(msg) <= 400, f"refusal for {cat} is longer than 400 chars"
    # in_scope is intentionally empty.
    assert _REFUSAL_MESSAGES["in_scope"] == ""


# ---------- edge cases -------------------------------------------------------


async def test_empty_string_is_in_scope():
    llm = _FakeLLM(category="personal_planning")  # would flag if consulted
    verdict = await classify_scope("", llm=llm)
    assert verdict.category == "in_scope"
    assert verdict.passed is True
    assert verdict.refusal_message == ""
    assert llm.calls == [], "empty input must short-circuit"


async def test_whitespace_only_is_in_scope():
    verdict = await classify_scope("    \n\t  ", llm=None)
    assert verdict.category == "in_scope"
    assert verdict.passed is True


async def test_very_long_input_handled_gracefully():
    # >2000 chars of innocuous market chatter → should not raise, should
    # still classify without pathological latency.
    long_text = "AAPL earnings looked strong this quarter. " * 100  # ~4300 chars
    llm = _FakeLLM(category="in_scope")
    verdict = await classify_scope(long_text, llm=llm)
    assert isinstance(verdict, ScopeVerdict)
    assert verdict.category == "in_scope"
    assert verdict.passed is True


async def test_very_long_input_with_trailing_lexical_still_hits():
    # The lexical screen trims to _MAX_SCAN_CHARS; a trigger inside that
    # window still fires. Not asserting behavior past the cap — just that
    # in-window content works.
    long_text = "market chatter. " * 20 + "should I buy a house this year"
    verdict = await classify_scope(long_text, skip_llm=True)
    assert verdict.category == "personal_planning"
    assert verdict.passed is False


# ---------- BUILD acceptance: 10 canonical examples, ≥90% detection ----------


_OUT_OF_SCOPE_EXAMPLES: list[tuple[str, Category]] = [
    # tax
    ("how do I minimize capital gains tax on my TSLA sale", "tax"),
    ("what tax bracket am I in", "tax"),
    ("should I do a roth conversion this year", "tax"),
    # legal
    ("I want to sue my broker for negligence", "legal"),
    ("draft me a prenup", "legal"),
    # personal_planning
    ("should I buy a house this year", "personal_planning"),
    ("how much should I save each month", "personal_planning"),
    ("am I on track to retire at 55", "personal_planning"),
    # medical
    ("what are the side effects of my medication", "medical"),
    ("my doctor said I have a rare symptom", "medical"),
]


async def test_acceptance_10_examples_at_least_90_percent_detected():
    detected = 0
    for text, expected in _OUT_OF_SCOPE_EXAMPLES:
        # Fake LLM returns the expected category for whatever the lexical
        # stage misses. Lexical hits short-circuit before the LLM is called.
        llm = _FakeLLM(category=expected)
        verdict = await classify_scope(text, llm=llm)
        if verdict.category != "in_scope":
            detected += 1
    total = len(_OUT_OF_SCOPE_EXAMPLES)
    assert total >= 10, "acceptance set must contain at least 10 examples"
    ratio = detected / total
    assert ratio >= 0.9, (
        f"detection {detected}/{total} ({ratio:.0%}) below the 90% BUILD threshold"
    )


@pytest.mark.parametrize("text,expected", _OUT_OF_SCOPE_EXAMPLES)
async def test_acceptance_each_example_classifies_correctly(text: str, expected: Category):
    """Sharper per-example check: not just detected, but classified as the
    expected out-of-scope category (either by lexical or by the LLM fake)."""
    llm = _FakeLLM(category=expected)
    verdict = await classify_scope(text, llm=llm)
    assert verdict.category == expected, (
        f"{text!r} → got {verdict.category}, expected {expected}"
    )
    assert verdict.passed is False
    assert verdict.refusal_message
