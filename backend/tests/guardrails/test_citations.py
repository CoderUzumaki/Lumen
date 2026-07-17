"""Hermetic tests for GRD-02 — the citation-required validator.

No network, no LLM. Exercises real ``Citation`` schema objects so the tests
also protect against schema drift.
"""
from __future__ import annotations

import pytest

from app.guardrails.citations import (
    CitationVerdict,
    SourceStub,
    check_citations,
)
from app.schemas.impact import Citation


def _make_citation(
    *,
    url: str,
    quote: str,
    source: str = "Reuters",
    title: str = "A test article",
) -> Citation:
    return Citation(source=source, url=url, title=title, quote=quote)


# --- Rule 1: at least one citation --------------------------------------


def test_empty_citation_list_fails() -> None:
    verdict = check_citations([], allowed_stubs=[])
    assert isinstance(verdict, CitationVerdict)
    assert verdict.passed is False
    assert any("no citations" in r.lower() for r in verdict.reasons)


# --- Happy path ---------------------------------------------------------


def test_single_matching_citation_passes() -> None:
    body = (
        "Acme Corp reported record quarterly earnings on Tuesday. "
        "Revenue rose 12% year over year."
    )
    stub = SourceStub(url="https://example.com/acme", body=body)
    citation = _make_citation(
        url="https://example.com/acme",
        quote="Revenue rose 12% year over year.",
    )

    verdict = check_citations([citation], allowed_stubs=[stub])

    assert verdict.passed is True
    assert verdict.reasons == []


# --- Rule 2: URL matching -----------------------------------------------


def test_url_mismatch_fails_and_names_offender() -> None:
    stub = SourceStub(
        url="https://example.com/foo",
        body="Some allowed body copy.",
    )
    citation = _make_citation(
        url="https://other.example.com/bar",
        quote="Some allowed body copy.",
    )

    verdict = check_citations([citation], allowed_stubs=[stub])

    assert verdict.passed is False
    joined = " ".join(verdict.reasons)
    assert "other.example.com/bar" in joined


def test_url_normalization_trailing_slash_and_scheme_case() -> None:
    # Stub URL is deliberately messy: uppercase host + scheme + trailing slash
    # + fragment. Normalization should still let the citation match.
    stub = SourceStub(
        url="HTTPS://EXAMPLE.COM/Article/#top",
        body="The market moved sharply after the announcement.",
    )
    # The pydantic Citation URL will already be scheme+host lowercased, but
    # we keep the trailing slash off to exercise the trailing-slash rule too.
    citation = _make_citation(
        url="https://example.com/Article",
        quote="The market moved sharply after the announcement.",
    )

    verdict = check_citations([citation], allowed_stubs=[stub])

    assert verdict.passed is True, verdict.reasons
    assert verdict.reasons == []


def test_case_sensitive_path_does_not_match() -> None:
    stub = SourceStub(
        url="https://example.com/path",
        body="body content here",
    )
    citation = _make_citation(
        url="https://example.com/Path",
        quote="body content here",
    )

    verdict = check_citations([citation], allowed_stubs=[stub])

    assert verdict.passed is False
    joined = " ".join(verdict.reasons)
    assert "https://example.com/Path" in joined


# --- Rule 3: quote substring after WS normalization ---------------------


def test_quote_matches_after_whitespace_normalization() -> None:
    # Body has messy multi-line whitespace; the LLM's quote uses a single
    # space. After normalization both should collapse to the same text.
    body = (
        "The Fed announced a\n\n"
        "surprise    rate cut of 25\tbasis   points\n"
        "on Wednesday afternoon."
    )
    stub = SourceStub(url="https://example.com/fed", body=body)
    citation = _make_citation(
        url="https://example.com/fed",
        quote="surprise rate cut of 25 basis points",
    )

    verdict = check_citations([citation], allowed_stubs=[stub])

    assert verdict.passed is True, verdict.reasons
    assert verdict.reasons == []


def test_quote_not_in_body_fails() -> None:
    stub = SourceStub(
        url="https://example.com/x",
        body="Real body text, nothing exotic.",
    )
    citation = _make_citation(
        url="https://example.com/x",
        quote="This sentence was never in the body.",
    )

    verdict = check_citations([citation], allowed_stubs=[stub])

    assert verdict.passed is False
    joined = " ".join(verdict.reasons)
    assert "https://example.com/x" in joined
    assert any("quote" in r.lower() for r in verdict.reasons)


# --- Aggregation over multiple citations --------------------------------


def test_multiple_citations_one_bad_only_bad_reported() -> None:
    stub_a = SourceStub(
        url="https://a.example.com/story",
        body="Alpha content appears here.",
    )
    stub_b = SourceStub(
        url="https://b.example.com/story",
        body="Beta content appears here.",
    )
    good_a = _make_citation(
        url="https://a.example.com/story",
        quote="Alpha content appears here.",
    )
    good_b = _make_citation(
        url="https://b.example.com/story",
        quote="Beta content appears here.",
    )
    bad = _make_citation(
        url="https://a.example.com/story",
        quote="This quote is not in either body.",
    )

    verdict = check_citations(
        [good_a, bad, good_b],
        allowed_stubs=[stub_a, stub_b],
    )

    assert verdict.passed is False
    # Only the bad citation (index 1) should be mentioned.
    assert len(verdict.reasons) == 1
    assert "citation[1]" in verdict.reasons[0]


# --- Empty-quote carve-out ----------------------------------------------


def test_empty_quote_passes_but_is_flagged() -> None:
    stub = SourceStub(
        url="https://example.com/story",
        body="The body content is entirely irrelevant here.",
    )
    citation = _make_citation(
        url="https://example.com/story",
        quote="",
    )

    verdict = check_citations([citation], allowed_stubs=[stub])

    assert verdict.passed is True
    assert len(verdict.reasons) == 1
    assert "empty quote" in verdict.reasons[0].lower()


# --- Combined: empty quote plus a real failure --------------------------


def test_empty_quote_does_not_mask_other_failure() -> None:
    """Sanity: an empty-quote advisory shouldn't rescue a hard failure elsewhere."""
    stub = SourceStub(
        url="https://example.com/ok",
        body="Body here.",
    )
    citation_empty = _make_citation(url="https://example.com/ok", quote="")
    citation_bad = _make_citation(
        url="https://elsewhere.example.com/nope",
        quote="Body here.",
    )

    verdict = check_citations(
        [citation_empty, citation_bad],
        allowed_stubs=[stub],
    )

    assert verdict.passed is False
    # Two reasons: one advisory, one hard failure.
    assert any("empty quote" in r.lower() for r in verdict.reasons)
    assert any("elsewhere.example.com" in r for r in verdict.reasons)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
