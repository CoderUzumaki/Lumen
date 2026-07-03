"""ING-04 acceptance for the GDELT adapter."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest

from app.pipelines.sources.gdelt import GDELTSource


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


def _ok(articles: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"articles": articles})


def _fail(status: int) -> httpx.Response:
    return httpx.Response(status, text=f"upstream {status}")


SAMPLE_ARTICLES = [
    {
        "url": "https://reuters.example/fed",
        "url_mobile": "",
        "title": "Fed hikes 25bps",
        "seendate": "20260703T130000Z",
        "socialimage": "",
        "domain": "reuters.com",
        "language": "English",
        "sourcecountry": "UnitedStates",
    },
    {
        "url": "https://bloomberg.example/oil",
        "title": "Oil retreats",
        "seendate": "20260703T140500Z",
        "domain": "bloomberg.com",
        "language": "English",
        "sourcecountry": "UnitedStates",
    },
]


async def test_fetch_maps_articles_correctly(monkeypatch):
    # Neuter the inter-request sleep so the test runs fast.
    monkeypatch.setattr("app.pipelines.sources.gdelt._MIN_INTERVAL_S", 0.0)
    # Reset last-call timestamp so we don't inherit state from a prior test.
    GDELTSource._last_call_ts = 0.0

    http, calls = _mk_http([_ok(SAMPLE_ARTICLES)])
    src = GDELTSource(http_client=http)

    items = await src.fetch(since=datetime(2026, 7, 3, tzinfo=timezone.utc))

    assert len(items) == 2
    assert items[0].source == "gdelt"
    assert items[0].source_id is None
    assert items[0].title == "Fed hikes 25bps"
    assert items[0].body is None
    assert items[0].published_at == datetime(2026, 7, 3, 13, 0, 0, tzinfo=timezone.utc)
    assert items[0].hints == {"domain": "reuters.com"}

    p = calls[0]["params"]
    assert p["mode"] == "ArtList"
    assert p["format"] == "JSON"
    assert p["sort"] == "DateDesc"
    assert p["maxrecords"] == 250
    assert p["startdatetime"] == "20260703000000"


async def test_since_filter_drops_older_items(monkeypatch):
    monkeypatch.setattr("app.pipelines.sources.gdelt._MIN_INTERVAL_S", 0.0)
    GDELTSource._last_call_ts = 0.0

    articles = [
        {  # older than since
            "url": "https://old.example",
            "title": "Older news",
            "seendate": "20260701T090000Z",
            "domain": "old.com",
        },
        SAMPLE_ARTICLES[0],  # in-range
    ]
    http, _ = _mk_http([_ok(articles)])
    src = GDELTSource(http_client=http)

    items = await src.fetch(since=datetime(2026, 7, 3, tzinfo=timezone.utc))

    assert len(items) == 1
    assert items[0].title == "Fed hikes 25bps"


async def test_429_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr("app.pipelines.sources.gdelt._MIN_INTERVAL_S", 0.0)
    GDELTSource._last_call_ts = 0.0

    http, calls = _mk_http([_fail(429), _ok(SAMPLE_ARTICLES[:1])])
    src = GDELTSource(http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert len(items) == 1
    assert len(calls) == 2


async def test_exhausted_retries_returns_empty(monkeypatch):
    monkeypatch.setattr("app.pipelines.sources.gdelt._MIN_INTERVAL_S", 0.0)
    GDELTSource._last_call_ts = 0.0

    http, _ = _mk_http([_fail(500), _fail(500), _fail(500)])
    src = GDELTSource(http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert items == []


async def test_malformed_seendate_is_skipped_not_fatal(monkeypatch):
    monkeypatch.setattr("app.pipelines.sources.gdelt._MIN_INTERVAL_S", 0.0)
    GDELTSource._last_call_ts = 0.0

    bad = {
        "url": "https://bad.example",
        "title": "Bad date",
        "seendate": "not-a-date",
        "domain": "bad.com",
    }
    http, _ = _mk_http([_ok([bad, SAMPLE_ARTICLES[0]])])
    src = GDELTSource(http_client=http)

    items = await src.fetch(since=datetime(2026, 7, 3, tzinfo=timezone.utc))

    assert len(items) == 1
    assert items[0].title == "Fed hikes 25bps"


async def test_semaphore_serializes_calls(monkeypatch):
    """Two concurrent fetches must be serialized by the class semaphore."""
    monkeypatch.setattr("app.pipelines.sources.gdelt._MIN_INTERVAL_S", 0.0)
    GDELTSource._last_call_ts = 0.0

    in_flight = 0
    peak = 0
    lock = asyncio.Lock()

    async def slow_get(url, params=None, **kwargs):
        nonlocal in_flight, peak
        async with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        async with lock:
            in_flight -= 1
        return _ok(SAMPLE_ARTICLES[:1])

    client_a = AsyncMock(spec=httpx.AsyncClient)
    client_a.get = AsyncMock(side_effect=slow_get)
    client_a.aclose = AsyncMock()
    client_b = AsyncMock(spec=httpx.AsyncClient)
    client_b.get = AsyncMock(side_effect=slow_get)
    client_b.aclose = AsyncMock()

    src_a = GDELTSource(http_client=client_a)
    src_b = GDELTSource(http_client=client_b)

    await asyncio.gather(
        src_a.fetch(since=datetime.now(timezone.utc)),
        src_b.fetch(since=datetime.now(timezone.utc)),
    )

    assert peak == 1, f"expected serialized calls, saw peak concurrency {peak}"


@pytest.mark.integration
async def test_live_gdelt_returns_items():
    """Live probe. Skipped by default; opt in with `pytest -m integration`."""
    src = GDELTSource()
    try:
        items = await src.fetch(
            since=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        )
        assert len(items) >= 10, f"expected >=10 items, got {len(items)}"
    finally:
        await src.aclose()
