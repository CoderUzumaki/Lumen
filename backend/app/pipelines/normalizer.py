"""News item normalization (ING-08).

`normalize(item)` produces a `NormalizedItem` — the shape `persist()` writes
to `news_items`. Steps:

1. Canonicalize the URL: lowercase host, drop fragment, drop every query
   param except `id` (the one param that meaningfully changes content).
2. `url_hash = sha256(canonical_url)` — matches the `news_items.url_hash`
   UNIQUE for idempotent insert.
3. Strip HTML from the body via `selectolax` (best-effort — malformed HTML
   falls back to raw).
4. Truncate body to 8000 chars.
5. Extract tickers: regex `\\b[A-Z]{1,5}(?:\\.[A-Z])?\\b` intersected with
   the caller-supplied `known_tickers` set (typically the union of all users'
   position tickers). Also picks up any ticker the adapter pre-hinted (per
   ING-03's `hints["tickers"]`) if it's in the known set.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from selectolax.parser import HTMLParser

from app.schemas.news import NewsItemIn, NewsSource

_TICKER_RE = re.compile(r"\b[A-Z]{1,5}(?:\.[A-Z])?\b")
_MAX_BODY_CHARS = 8000


def _canonical_url(url: str) -> str:
    parsed = urlparse(url)
    kept = [(k, v) for k, v in parse_qsl(parsed.query) if k == "id"]
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            urlencode(kept),
            "",  # drop fragment
        )
    )


def _url_hash(url: str) -> str:
    return hashlib.sha256(_canonical_url(url).encode("utf-8")).hexdigest()


def _strip_html(text: str | None) -> str | None:
    if not text:
        return None
    try:
        cleaned = HTMLParser(text).text(separator=" ", strip=True)
    except Exception:
        return text
    return cleaned or None


def _extract_tickers(haystack: str, known: set[str]) -> list[str]:
    if not haystack or not known:
        return []
    hits = {m.group(0) for m in _TICKER_RE.finditer(haystack)}
    return sorted(hits & known)


@dataclass
class NormalizedItem:
    """Ready-to-persist news item."""

    source: NewsSource
    source_id: str | None
    url: str
    url_hash: str
    title: str
    body: str | None
    published_at: datetime
    raw_payload: dict[str, Any]
    hints: dict[str, Any]
    tickers: list[str] = field(default_factory=list)


def normalize(
    item: NewsItemIn, *, known_tickers: set[str] | None = None
) -> NormalizedItem:
    known = known_tickers or set()
    url = str(item.url)

    cleaned_body = _strip_html(item.body)
    if cleaned_body and len(cleaned_body) > _MAX_BODY_CHARS:
        cleaned_body = cleaned_body[:_MAX_BODY_CHARS]

    haystack = " ".join(filter(None, [item.title, cleaned_body]))
    regex_hits = _extract_tickers(haystack, known)

    hint_tickers = [t for t in (item.hints.get("tickers") or []) if t in known]
    all_tickers = sorted(set(regex_hits) | set(hint_tickers))

    return NormalizedItem(
        source=item.source,
        source_id=item.source_id,
        url=url,
        url_hash=_url_hash(url),
        title=item.title,
        body=cleaned_body,
        published_at=item.published_at,
        raw_payload=item.raw_payload,
        hints=item.hints,
        tickers=all_tickers,
    )
