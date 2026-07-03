"""ING-03 acceptance for the Marketaux adapter."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx

from app.pipelines.sources.marketaux import MarketauxSource


def _mk_http(responses: list):
    calls: list[dict] = []

    async def get(url, params=None, **kwargs):
        calls.append({"url": url, "params": params or {}})
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=get)
    client.aclose = AsyncMock()
    return client, calls


def _ok(rows: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"data": rows})


def _fail(status: int) -> httpx.Response:
    return httpx.Response(status, text=f"upstream {status}")


SAMPLE_ROWS = [
    {
        "uuid": "abc-123",
        "title": "Apple beats Q4 expectations",
        "description": "Apple reported earnings above consensus.",
        "url": "https://marketaux.example/aapl",
        "published_at": "2026-07-03T13:00:00Z",
        "source": "reuters.com",
        "entities": [
            {"symbol": "AAPL", "type": "equity", "sentiment_score": 0.7},
            {"symbol": "MSFT", "type": "equity", "sentiment_score": 0.1},
            {"symbol": "AAPL", "type": "equity"},  # duplicate — should dedup
        ],
    },
    {
        "uuid": "def-456",
        "title": "Oil declines",
        "snippet": "Oil dropped 2% today.",  # snippet fallback
        "url": "https://marketaux.example/oil",
        "published_at": "2026-07-03T14:00:00Z",
        "source": "bloomberg.com",
        "entities": [],  # no entities → hints stays {}
    },
]


async def test_hints_tickers_populated_from_entities():
    http, calls = _mk_http([_ok(SAMPLE_ROWS)])
    src = MarketauxSource(api_key="live-key", http_client=http)

    items = await src.fetch(since=datetime(2026, 7, 3, tzinfo=timezone.utc))

    assert len(items) == 2

    # First item: entities → hints["tickers"] with dedup + order preservation.
    assert items[0].source == "marketaux"
    assert items[0].source_id == "abc-123"
    assert items[0].title == "Apple beats Q4 expectations"
    assert items[0].hints == {"tickers": ["AAPL", "MSFT"]}

    # Second item: no entities → hints is empty (never None).
    assert items[1].hints == {}
    # Body falls back from `description` to `snippet` when description absent.
    assert items[1].body == "Oil dropped 2% today."

    # Query params match the spec.
    p = calls[0]["params"]
    assert p["filter_entities"] == "true"
    assert p["language"] == "en"
    assert p["limit"] == 50
    assert p["api_token"] == "live-key"
    assert p["published_after"].startswith("2026-07-03T00:00:00")


async def test_missing_api_key_returns_empty_no_exception():
    http, calls = _mk_http([_ok(SAMPLE_ROWS)])
    src = MarketauxSource(api_key=None, http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert items == []
    assert calls == []


async def test_429_retried_then_succeeds():
    http, calls = _mk_http([_fail(429), _ok(SAMPLE_ROWS[:1])])
    src = MarketauxSource(api_key="live-key", http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert len(items) == 1
    assert len(calls) == 2


async def test_exhausted_retries_returns_empty():
    http, _ = _mk_http([_fail(500), _fail(500), _fail(500)])
    src = MarketauxSource(api_key="live-key", http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert items == []


async def test_non_retryable_4xx_returns_empty():
    http, _ = _mk_http([_fail(401)])
    src = MarketauxSource(api_key="live-key", http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert items == []


async def test_malformed_row_is_skipped_not_fatal():
    bad = {"missing": "url"}  # no url / no title
    good = SAMPLE_ROWS[0]
    http, _ = _mk_http([_ok([bad, good])])
    src = MarketauxSource(api_key="live-key", http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert len(items) == 1
    assert items[0].source_id == "abc-123"
