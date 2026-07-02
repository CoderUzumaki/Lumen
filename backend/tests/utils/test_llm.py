"""BOOT-06 acceptance tests for the free-tier LLM wrapper."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import BaseModel

from app.utils.llm import LLMClient, LLMResponse, Message


class _Item(BaseModel):
    name: str
    qty: int


def _ok_resp(content: str, usage: dict | None = None) -> httpx.Response:
    body = {
        "choices": [{"message": {"content": content}}],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5},
    }
    return httpx.Response(200, json=body)


def _fail_resp(status: int) -> httpx.Response:
    return httpx.Response(status, text=f"upstream said {status}")


def _mk_http(responses: list):
    """Build a fake `httpx.AsyncClient` that returns `responses` in order."""
    calls: list[tuple[str, dict | None]] = []

    async def post(url, json=None, **kwargs):
        calls.append((url, json))
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=post)
    client.aclose = AsyncMock()
    return client, calls


async def test_happy_path():
    http, calls = _mk_http([_ok_resp("hello world")])
    client = LLMClient(http_client=http)
    with patch("app.utils.llm.LLMClient._record_call", new=AsyncMock()), patch(
        "app.utils.llm.rate_limit_acquire", new=AsyncMock()
    ):
        resp = await client.complete([Message("user", "hi")], tier="fast")
    assert resp.content == "hello world"
    assert resp.prompt_tokens == 10
    assert resp.completion_tokens == 5
    assert resp.cache_hit is False
    assert len(calls) == 1


async def test_retry_on_5xx():
    """Two 503s should be retried, third response succeeds."""
    http, calls = _mk_http([_fail_resp(503), _fail_resp(502), _ok_resp("ok")])
    client = LLMClient(http_client=http)
    with patch("app.utils.llm.LLMClient._record_call", new=AsyncMock()), patch(
        "app.utils.llm.rate_limit_acquire", new=AsyncMock()
    ):
        resp = await client.complete([Message("user", "hi")])
    assert resp.content == "ok"
    assert len(calls) == 3


async def test_structured_output_json_parse_retry():
    """A non-JSON reply triggers a retry when `response_model` is set."""
    http, calls = _mk_http(
        [_ok_resp("not-json-at-all"), _ok_resp('{"name": "x", "qty": 3}')]
    )
    client = LLMClient(http_client=http)
    with patch("app.utils.llm.LLMClient._record_call", new=AsyncMock()), patch(
        "app.utils.llm.rate_limit_acquire", new=AsyncMock()
    ):
        resp = await client.complete(
            [Message("user", "give me x")],
            response_model=_Item,
            tier="fast",
        )
    assert isinstance(resp.parsed, _Item)
    assert resp.parsed.name == "x"
    assert resp.parsed.qty == 3
    assert len(calls) == 2


async def test_rate_limit_backoff_triggers():
    """The token bucket blocks the third acquire when RPM=2."""
    from app.utils.rate_limit import RateLimiter

    limiter = RateLimiter(rpm_map={"default": 2, "m": 2}, queue_cap=10)

    await limiter.acquire("m")
    await limiter.acquire("m")
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(limiter.acquire("m"), timeout=0.15)


async def test_rate_limit_queue_cap_raises():
    """Queue over capacity raises RateLimitExceeded instead of blocking forever."""
    from app.utils.rate_limit import RateLimiter, RateLimitExceeded

    limiter = RateLimiter(rpm_map={"default": 1, "m": 1}, queue_cap=0)
    await limiter.acquire("m")  # fills the bucket
    with pytest.raises(RateLimitExceeded):
        await limiter.acquire("m")  # queue_cap=0 → immediate raise


async def test_semantic_cache_hit_skips_network(monkeypatch):
    """When _cache_lookup returns a hit, no HTTP call is made.

    BOOT-06 stubs _cache_lookup to always return None; OPT-05 fills it in.
    This test proves the stub is wired correctly by monkey-patching a hit.
    """
    http, calls = _mk_http([_ok_resp("SHOULD NOT BE USED")])
    client = LLMClient(http_client=http)

    fake = LLMResponse(
        content="cached content",
        parsed=None,
        model="anything",
        tier="fast",
        prompt_tokens=None,
        completion_tokens=None,
        latency_ms=0,
        cache_hit=True,
        cache_source="semantic",
    )

    async def cache_hit(cache_key, messages):
        return fake

    monkeypatch.setattr(client, "_cache_lookup", cache_hit)

    with patch("app.utils.llm.LLMClient._record_call", new=AsyncMock()), patch(
        "app.utils.llm.rate_limit_acquire", new=AsyncMock()
    ):
        resp = await client.complete(
            [Message("user", "cached?")],
            cache_key="test-key",
        )

    assert resp.cache_hit is True
    assert resp.cache_source == "semantic"
    assert resp.content == "cached content"
    assert len(calls) == 0  # crucial: no network round-trip


async def test_records_row_per_uncached_call():
    """Every non-cached call inserts a row into `llm_calls`."""
    http, _ = _mk_http([_ok_resp("hi", usage={"prompt_tokens": 7, "completion_tokens": 3})])
    client = LLMClient(http_client=http)
    record = AsyncMock()
    with patch("app.utils.llm.LLMClient._record_call", new=record), patch(
        "app.utils.llm.rate_limit_acquire", new=AsyncMock()
    ):
        await client.complete([Message("user", "hi")], agent_name="test-agent")
    assert record.await_count == 1
    kwargs = record.await_args.kwargs
    assert kwargs["agent_name"] == "test-agent"


@pytest.mark.free_tier_live
async def test_openrouter_live_probe():
    """Live integration test against real OpenRouter free-tier models.

    Skipped by default (marker `free_tier_live`). Runs when explicitly
    selected:  `pytest -m free_tier_live tests/utils/test_llm.py`.
    """
    import os as _os

    if not _os.environ.get("OPENROUTER_API_KEY") or _os.environ.get(
        "OPENROUTER_API_KEY"
    ) == "test-openrouter-key":
        pytest.skip("no live OPENROUTER_API_KEY configured")

    client = LLMClient()
    try:
        fast = await client.complete(
            [Message("user", "Reply with exactly the word: ping")],
            tier="fast",
            max_tokens=8,
            temperature=0.0,
        )
        assert fast.content

        thorough = await client.complete(
            [Message("user", "Reply with exactly the word: ping")],
            tier="thorough",
            max_tokens=8,
            temperature=0.0,
        )
        assert thorough.content
    finally:
        await client.aclose()
