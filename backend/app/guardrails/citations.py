"""GRD-02 — citation-required validator.

PRD Section 8, principle #1: every claim in an ``ImpactAssessment`` must cite
a source that was actually supplied to the LLM. This module is the validator
that runs at the LLM-output boundary.

The validator takes:

* the ``Citation`` objects the LLM produced, and
* the ``SourceStub`` objects (url + body) the caller injected into the prompt

and returns a ``CitationVerdict`` describing whether the citations are
grounded in the supplied stubs.

Rules (all must pass for ``passed=True``):

1. At least one citation.
2. Every citation URL matches at least one ``SourceStub`` URL, after
   normalization (see :func:`_normalize_url`).
3. Every non-empty citation quote is a whitespace-normalized substring of the
   corresponding source stub's whitespace-normalized body.

An empty ``quote`` skips rule 3 for that citation but does not fail the
verdict; it is flagged in ``reasons`` as an advisory so the caller can
downgrade later.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

from app.schemas.impact import Citation


@dataclass
class CitationVerdict:
    """Result of :func:`check_citations`.

    ``passed`` is True iff no hard rule failed. ``reasons`` holds one message
    per rule failure and per advisory (e.g. empty quote); it is empty when
    ``passed=True`` unless an advisory was emitted.
    """

    passed: bool
    reasons: list[str]


@dataclass
class SourceStub:
    """The (url, body) pair the LLM was allowed to cite from — one per news
    source the caller injected into the prompt."""

    url: str
    body: str


_WS_RE = re.compile(r"\s+")


def _normalize_url(raw: str) -> str:
    """Canonicalize a URL for citation-vs-stub matching.

    - Lowercase scheme and host (host is case-insensitive per RFC 3986).
    - Drop the fragment.
    - Strip a single trailing ``/`` from the path, unless the path is empty
      or just ``/``.
    - Preserve path and query casing (path comparison stays case-sensitive
      per the module contract).
    """
    parts = urlsplit(raw.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def _normalize_ws(raw: str) -> str:
    """Collapse whitespace runs to a single space and strip both ends."""
    return _WS_RE.sub(" ", raw).strip()


def check_citations(
    citations: Iterable[Citation],
    *,
    allowed_stubs: Iterable[SourceStub],
) -> CitationVerdict:
    """Validate LLM-produced citations against the source stubs from the prompt.

    See module docstring for the rule set.
    """
    citation_list = list(citations)
    stub_list = list(allowed_stubs)

    # Rule 1.
    if not citation_list:
        return CitationVerdict(passed=False, reasons=["no citations provided"])

    # Build a lookup keyed by the normalized stub URL. If the caller passes
    # duplicate URLs the last one wins — the caller is responsible for
    # deduping their stubs; this validator is not the place to argue.
    stub_index: dict[str, str] = {}
    for stub in stub_list:
        stub_index[_normalize_url(stub.url)] = _normalize_ws(stub.body)

    reasons: list[str] = []
    hard_failed = False

    for idx, citation in enumerate(citation_list):
        url_str = str(citation.url)
        norm_url = _normalize_url(url_str)

        # Rule 2.
        if norm_url not in stub_index:
            reasons.append(
                f"citation[{idx}] url {url_str!r} does not match any allowed source stub"
            )
            hard_failed = True
            continue

        # Rule 3 — with the empty-quote carve-out (advisory only).
        quote = citation.quote
        if _normalize_ws(quote) == "":
            reasons.append(f"citation[{idx}] empty quote (rule-3 skipped)")
            continue

        norm_quote = _normalize_ws(quote)
        norm_body = stub_index[norm_url]
        if norm_quote not in norm_body:
            reasons.append(
                f"citation[{idx}] quote not found in source body for url {url_str!r}"
            )
            hard_failed = True

    return CitationVerdict(passed=not hard_failed, reasons=reasons)
