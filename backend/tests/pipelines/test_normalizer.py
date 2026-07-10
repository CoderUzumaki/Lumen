"""ING-08 acceptance: normalizer tests."""
from __future__ import annotations

from datetime import datetime, timezone

from app.pipelines.normalizer import (
    _canonical_url,
    _extract_tickers,
    _url_hash,
    normalize,
)
from app.schemas.news import NewsItemIn


def test_canonical_url_lowercases_host_drops_fragment_and_extra_params():
    got = _canonical_url(
        "https://EXAMPLE.com/path?utm_source=twitter&id=42&other=x#frag"
    )
    assert got == "https://example.com/path?id=42"


def test_canonical_url_preserves_bare_path():
    assert _canonical_url("https://reuters.com/one") == "https://reuters.com/one"


def test_url_hash_is_stable_across_tracking_params():
    a = _url_hash("https://reuters.com/story?utm_source=x&id=1")
    b = _url_hash("https://reuters.com/story?utm_medium=email&id=1")
    assert a == b


def test_url_hash_differs_for_different_id():
    a = _url_hash("https://reuters.com/story?id=1")
    b = _url_hash("https://reuters.com/story?id=2")
    assert a != b


def test_extract_tickers_intersects_with_known():
    known = {"NVDA", "AAPL", "TSLA"}
    got = _extract_tickers("NVDA and AAPL announce AI partnership. IBM too.", known)
    assert got == ["AAPL", "NVDA"]  # sorted; IBM dropped (not in known set)


def test_extract_tickers_no_known_returns_empty():
    assert _extract_tickers("NVDA soars", set()) == []


def _mk_item(**overrides) -> NewsItemIn:
    base = {
        "source": "newsapi",
        "url": "https://reuters.com/story?id=1&utm_source=twitter",
        "title": "NVDA reports Q4 earnings",
        "body": "<p>NVDA and AAPL both rally.</p><script>bad()</script>",
        "published_at": datetime(2026, 7, 3, 12, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return NewsItemIn(**base)


def test_normalize_computes_url_hash_from_canonical_url():
    item = _mk_item()
    norm = normalize(item, known_tickers={"NVDA", "AAPL"})
    assert norm.url_hash == _url_hash("https://reuters.com/story?id=1")


def test_normalize_strips_html_from_body():
    item = _mk_item()
    norm = normalize(item, known_tickers={"NVDA", "AAPL"})
    assert norm.body is not None
    assert "<p>" not in norm.body
    assert "NVDA" in norm.body
    assert "AAPL" in norm.body


def test_normalize_extracts_tickers_from_title_and_body():
    item = _mk_item()
    norm = normalize(item, known_tickers={"NVDA", "AAPL", "MSFT"})
    assert set(norm.tickers) == {"NVDA", "AAPL"}


def test_normalize_truncates_body_to_8000_chars():
    long_body = "<p>" + ("x " * 5000) + "</p>"
    item = _mk_item(body=long_body)
    norm = normalize(item, known_tickers=set())
    assert norm.body is not None
    assert len(norm.body) <= 8000


def test_normalize_merges_hint_tickers_with_extracted():
    item = _mk_item(
        title="Fed hikes rates",
        body="<p>Nothing about NVDA here.</p>",
        hints={"tickers": ["NVDA", "XYZ"]},
    )
    known = {"NVDA", "AAPL"}
    norm = normalize(item, known_tickers=known)
    # NVDA came from hints (not in text); AAPL not present anywhere;
    # XYZ dropped because not in known.
    assert norm.tickers == ["NVDA"]


def test_normalize_preserves_other_fields():
    item = _mk_item()
    norm = normalize(item, known_tickers=set())
    assert norm.source == "newsapi"
    assert norm.title == "NVDA reports Q4 earnings"
    assert norm.published_at == datetime(2026, 7, 3, 12, tzinfo=timezone.utc)
