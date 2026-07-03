"""ING-02 acceptance for the NewsAPI adapter."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx

from app.pipelines.sources.newsapi import NewsAPISource


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


def _ok_response(articles: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"status": "ok", "articles": articles})


def _fail_response(status: int) -> httpx.Response:
    return httpx.Response(
        status,
        text=f"upstream {status}",
        headers={"X-RateLimit-Reset": "1720000000"},
    )


SAMPLE_ARTICLES = [
    {
        "source": {"id": "reuters", "name": "Reuters"},
        "author": "Reuters Staff",
        "title": "Fed hikes 25bps",
        "description": "The Federal Reserve raised rates by 25 basis points.",
        "url": "https://reuters.example/fed-hike",
        "publishedAt": "2026-07-03T13:30:00Z",
        "content": "Full body …",
    },
    {
        "source": {"id": None, "name": "Blog"},
        "author": None,
        "title": "NVDA surges on new chip",
        "description": None,
        "url": "https://blog.example/nvda",
        "publishedAt": "2026-07-03T14:00:00Z",
        "content": "…",
    },
    {
        "source": {"id": "bloomberg", "name": "Bloomberg"},
        "title": "Oil retreats",
        "description": "Oil retreats after…",
        "url": "https://bloomberg.example/oil",
        "publishedAt": "2026-07-03T15:00:00Z",
    },
]


async def test_fetch_maps_three_items_correctly():
    http, calls = _mk_http([_ok_response(SAMPLE_ARTICLES)])
    src = NewsAPISource(api_key="live-key", http_client=http)

    items = await src.fetch(since=datetime(2026, 7, 3, tzinfo=timezone.utc))

    assert len(items) == 3
    assert [i.title for i in items] == [
        "Fed hikes 25bps",
        "NVDA surges on new chip",
        "Oil retreats",
    ]
    assert items[0].source == "newsapi"
    assert items[0].source_id == "reuters"
    assert items[1].source_id is None  # missing id → None
    assert items[2].body == "Oil retreats after…"  # falls back to description
    assert items[0].raw_payload["author"] == "Reuters Staff"

    # 'from' param must be an ISO8601 string of `since`.
    assert calls[0]["params"]["from"].startswith("2026-07-03T00:00:00")
    assert calls[0]["params"]["apiKey"] == "live-key"


async def test_missing_api_key_returns_empty_no_exception():
    http, calls = _mk_http([_ok_response(SAMPLE_ARTICLES)])
    src = NewsAPISource(api_key=None, http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert items == []
    assert calls == []  # never even hits the network


async def test_429_is_retried_with_backoff_then_succeeds():
    http, calls = _mk_http(
        [_fail_response(429), _fail_response(429), _ok_response(SAMPLE_ARTICLES[:1])]
    )
    src = NewsAPISource(api_key="live-key", http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert len(items) == 1
    assert len(calls) == 3


async def test_exhausted_retries_returns_empty_not_raises():
    http, _ = _mk_http([_fail_response(500), _fail_response(500), _fail_response(500)])
    src = NewsAPISource(api_key="live-key", http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert items == []


async def test_non_retryable_4xx_returns_empty_not_raises():
    http, _ = _mk_http([_fail_response(400)])
    src = NewsAPISource(api_key="live-key", http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert items == []


async def test_malformed_article_is_skipped_not_fatal():
    good_article = SAMPLE_ARTICLES[0]
    bad_article = {"missing": "url"}  # No url — will raise KeyError when mapped
    http, _ = _mk_http([_ok_response([bad_article, good_article])])
    src = NewsAPISource(api_key="live-key", http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert len(items) == 1
    assert items[0].title == "Fed hikes 25bps"
