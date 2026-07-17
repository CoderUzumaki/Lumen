"""GRD-01 acceptance: lexical + LLM directional-language guardrail."""
from __future__ import annotations

from typing import Callable
from unittest.mock import AsyncMock

from app.guardrails.directional import (
    DirectionalVerdict,
    _DirectionalCheck,
    _FORBIDDEN_TOKENS,
    check_directional,
    lexical_check,
)
from app.utils.llm import LLMClient, LLMResponse, Message


# --- helpers ----------------------------------------------------------------


def _fake_llm(
    verdict_fn: Callable[[str], _DirectionalCheck],
) -> LLMClient:
    """LLMClient whose `.complete` returns a canned `_DirectionalCheck`.

    `verdict_fn(user_text) -> _DirectionalCheck` decides per-call. No network.
    """
    client = LLMClient(http_client=AsyncMock())  # http_client not touched

    async def _complete(messages: list[Message], **kwargs):
        user_text = ""
        for m in messages:
            if m.role == "user":
                user_text = m.content
        verdict = verdict_fn(user_text)
        return LLMResponse(
            content=verdict.model_dump_json(),
            parsed=verdict,
            model="fake",
            tier=kwargs.get("tier", "fast"),
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
        )

    client.complete = _complete  # type: ignore[assignment]
    return client


def _always_no_llm() -> LLMClient:
    return _fake_llm(
        lambda _t: _DirectionalCheck(recommends_action=False, rationale="mechanism only")
    )


def _always_yes_llm() -> LLMClient:
    return _fake_llm(
        lambda _t: _DirectionalCheck(
            recommends_action=True, rationale="text tells reader to act"
        )
    )


def _exploding_llm() -> LLMClient:
    """LLM whose `.complete` raises if invoked — used to prove short-circuit."""
    client = LLMClient(http_client=AsyncMock())

    async def _complete(*_a, **_k):  # pragma: no cover — invocation is a failure
        raise AssertionError("LLM should not have been called")

    client.complete = _complete  # type: ignore[assignment]
    return client


# --- lexical-only cases -----------------------------------------------------


def test_lexical_check_clean_mechanism_returns_empty():
    assert lexical_check("higher rates compress valuations") == []


def test_lexical_check_finds_buy_and_should():
    hits = lexical_check("you should buy TLT now")
    assert set(hits) == {"buy", "should"}


def test_lexical_check_is_deterministic_alphabetical():
    hits = lexical_check("you should buy TLT now")
    assert hits == sorted(hits)


def test_lexical_check_is_case_insensitive():
    hits = lexical_check("You SHOULD Buy TLT")
    assert set(hits) == {"buy", "should"}


def test_lexical_check_dedupes_repeats():
    hits = lexical_check("buy, then buy again, and buy some more")
    assert hits == ["buy"]


def test_lexical_check_respects_word_boundaries():
    # "trimming" should NOT match \btrim\b; "advice" should NOT match \badvise\b.
    assert lexical_check("consider trimming your exposure to advice") == ["consider"]


def test_lexical_check_covers_every_forbidden_token():
    # sanity: each token from the constant appears in isolation.
    for tok in _FORBIDDEN_TOKENS:
        assert tok in lexical_check(f"lorem {tok} ipsum")


# --- check_directional: skip_llm path ---------------------------------------


async def test_skip_llm_accepts_mechanism_text():
    v = await check_directional("higher rates compress valuations", skip_llm=True)
    assert v == DirectionalVerdict(
        passed=True, reason="", matched_tokens=[], llm_asked=False
    )


async def test_skip_llm_rejects_directional_text():
    v = await check_directional("you should buy TLT", skip_llm=True)
    assert v.passed is False
    assert "buy" in v.matched_tokens
    assert "should" in v.matched_tokens
    assert v.llm_asked is False
    assert v.reason and len(v.reason) <= 200


# --- check_directional: LLM interplay ---------------------------------------


async def test_lexical_hit_short_circuits_the_llm():
    llm = _exploding_llm()  # would raise if called
    v = await check_directional("we recommend NVDA at this level", llm=llm)
    assert v.passed is False
    assert "recommend" in v.matched_tokens
    assert v.llm_asked is False


async def test_llm_yes_causes_rejection():
    llm = _always_yes_llm()
    v = await check_directional(
        "rotate your allocation into technology exposure today", llm=llm
    )
    assert v.passed is False
    assert v.llm_asked is True
    assert v.matched_tokens == []
    assert v.reason and len(v.reason) <= 200


async def test_llm_no_causes_acceptance():
    llm = _always_no_llm()
    v = await check_directional(
        "higher rates historically compress duration-sensitive "
        "valuations by 3-5% over 30 days",
        llm=llm,
    )
    assert v.passed is True
    assert v.llm_asked is True
    assert v.matched_tokens == []
    assert v.reason == ""


async def test_missing_llm_without_skip_flag_falls_through_to_accept():
    # No lexical hit + no LLM available = accept (skip_llm effectively True).
    v = await check_directional("higher rates compress valuations", llm=None)
    assert v.passed is True
    assert v.llm_asked is False


# --- BUILD.md acceptance examples ------------------------------------------


async def test_build_acceptance_fed_cut_buy_tlt_is_rejected():
    # Lexical alone catches "should" + "buy".
    v = await check_directional(
        "the Fed cut suggests you should buy TLT", skip_llm=True
    )
    assert v.passed is False
    assert "buy" in v.matched_tokens
    assert "should" in v.matched_tokens


async def test_build_acceptance_mechanism_with_magnitude_is_accepted():
    llm = _always_no_llm()
    v = await check_directional(
        "higher rates historically compress duration-sensitive "
        "valuations by 3-5% over 30 days",
        llm=llm,
    )
    assert v.passed is True


# --- Accuracy over >=30 hand-crafted examples --------------------------------

# (text, expected_passed)
_EXAMPLES: list[tuple[str, bool]] = [
    # --- Mechanism / magnitude sentences (should PASS) ---
    ("higher rates historically compress duration-sensitive valuations by 3-5% over 30 days", True),
    ("FOMC tightening cycles have coincided with 8-12% multiple compression", True),
    ("Rising Treasury yields typically pressure growth equity multiples", True),
    ("Oil prices above $90 correlate with 2-3% CPI upside surprises", True),
    ("Dollar strength coincides with EM equity underperformance historically", True),
    ("Credit spreads widening 50bps has preceded recessions by 3-6 months", True),
    ("Yield curve inversion has preceded 8 of the last 10 recessions", True),
    ("Semiconductor cyclicality shows peak-to-trough drawdowns near 40%", True),
    ("Historically, a Fed pause has coincided with equity multiple expansion", True),
    ("BoJ yield-curve-control changes ripple through global rate markets", True),
    ("US CPI at 4.1% remains above the Fed's 2% target", True),
    ("OPEC production cuts of 1M bpd have historically added $8-10 to Brent", True),
    ("Copper prices lead global manufacturing PMIs by roughly three months", True),
    ("Gold tends to outperform when real yields fall", True),
    ("The market reacted to the announcement with a 2% decline", True),
    ("Analysts are watching closely for the next inflation print", True),
    ("Realized volatility has increased 30% year to date", True),
    ("This is not financial advice", True),
    ("Historical betas suggest 0.85 sensitivity to the 10-year yield", True),
    ("Rate-cut cycles have coincided with duration outperformance in past episodes", True),

    # --- Directional with forbidden tokens (rejected by LEXICAL) ---
    ("you should buy TLT now", False),
    ("we recommend you add to your NVDA position", False),
    ("sell your bond position immediately", False),
    ("consider your exposure to technology", False),
    ("the Fed cut suggests you should buy TLT", False),
    ("we advise overweight technology exposure", False),
    ("go long on gold here", False),
    ("short the euro against the dollar", False),
    ("hold your position for now", False),
    ("underweight EM equities in this environment", False),
    ("we are bullish on semiconductors", False),
    ("bearish on regional banks near-term", False),

    # --- Subtle recommendations WITHOUT forbidden tokens (LLM catches) ---
    ("increase your allocation to equities today", False),
    ("reduce your exposure to bonds immediately", False),
    ("it is time to rotate out of technology names", False),
    ("raise your position size in NVDA", False),
    ("cut your allocation to emerging markets", False),
]


# Substring keys the fake LLM should flag as directional (used in the accuracy
# test). Everything else the LLM sees returns NO (accepted).
_LLM_YES_SUBSTRINGS = frozenset(
    {
        "increase your allocation to equities today",
        "reduce your exposure to bonds immediately",
        "it is time to rotate out of technology names",
        "raise your position size in NVDA",
        "cut your allocation to emerging markets",
    }
)


def _lookup_llm() -> LLMClient:
    def _verdict(user_text: str) -> _DirectionalCheck:
        for key in _LLM_YES_SUBSTRINGS:
            if key in user_text:
                return _DirectionalCheck(
                    recommends_action=True,
                    rationale="LLM flagged subtle recommendation",
                )
        return _DirectionalCheck(recommends_action=False, rationale="mechanism only")

    return _fake_llm(_verdict)


async def test_accuracy_over_hand_crafted_examples():
    llm = _lookup_llm()
    total = len(_EXAMPLES)
    assert total >= 30, f"need >=30 examples, have {total}"

    correct = 0
    misses: list[tuple[str, bool, bool]] = []
    for text, expected in _EXAMPLES:
        v = await check_directional(text, llm=llm)
        if v.passed == expected:
            correct += 1
        else:
            misses.append((text, expected, v.passed))

    accuracy = correct / total
    assert accuracy >= 0.95, (
        f"accuracy {accuracy:.2%} ({correct}/{total}) below 95% threshold. "
        f"misses={misses}"
    )
