"""NewsAPI.org adapter (ING-02).

Free tier: 100 requests/day. This is the flakiest of our five sources — do
NOT fail hard when the key is missing or the daily budget is exhausted.

Endpoint: `https://newsapi.org/v2/everything`
Query params: `q="finance OR markets OR stocks OR fed OR earnings"`,
`language=en`, `sortBy=publishedAt`, `pageSize=100`, `from=<since ISO8601>`.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.pipelines.sources.base import BaseSource
from app.schemas.news import NewsItemIn
from app.utils.config import Config

log = logging.getLogger(__name__)

_ENDPOINT = "https://newsapi.org/v2/everything"
_DEFAULT_QUERY = "finance OR markets OR stocks OR fed OR earnings"


class _RetryableError(Exception):
    """Signals to tenacity we should retry — 429, 5xx, or transport error."""


class NewsAPISource(BaseSource):
    source_name = "newsapi"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        page_size: int = 100,
        query: str = _DEFAULT_QUERY,
    ):
        self._api_key = api_key if api_key is not None else Config.NEWSAPI_KEY
        self._http = http_client
        self._own_http = http_client is None
        self._page_size = page_size
        self._query = query

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def aclose(self) -> None:
        if self._http is not None and self._own_http:
            await self._http.aclose()
            self._http = None

    async def fetch(self, since: datetime) -> list[NewsItemIn]:
        if not self._api_key:
            log.warning("newsapi: NEWSAPI_KEY not configured — skipping")
            return []

        params = {
            "q": self._query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": self._page_size,
            "from": since.isoformat(),
            "apiKey": self._api_key,
        }

        try:
            data = await self._call_with_retry(params)
        except RetryError:
            log.warning("newsapi: exhausted retries; returning empty list")
            return []
        except Exception:  # pragma: no cover — defensive
            log.exception("newsapi: unexpected error; returning empty list")
            return []

        articles = data.get("articles") or []
        items: list[NewsItemIn] = []
        for a in articles:
            try:
                items.append(self._to_news_item(a))
            except Exception:
                # Skip any single malformed article — never let one bad row
                # kill the whole fetch.
                log.exception("newsapi: could not parse article; skipping")
        return items

    def _to_news_item(self, article: dict[str, Any]) -> NewsItemIn:
        return NewsItemIn(
            source="newsapi",
            source_id=(article.get("source") or {}).get("id"),
            url=article["url"],
            title=article["title"],
            body=article.get("content") or article.get("description"),
            published_at=article["publishedAt"],
            raw_payload=article,
        )

    async def _call_with_retry(self, params: dict[str, Any]) -> dict[str, Any]:
        retrying = AsyncRetrying(
            reraise=True,
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8.0),
            retry=retry_if_exception_type(_RetryableError),
        )
        async for attempt in retrying:
            with attempt:
                return await self._one_call(params)
        raise RetryError(  # pragma: no cover — reraise=True
            last_attempt=None  # type: ignore[arg-type]
        )

    async def _one_call(self, params: dict[str, Any]) -> dict[str, Any]:
        http = await self._get_http()
        try:
            resp = await http.get(_ENDPOINT, params=params)
        except httpx.HTTPError as e:
            raise _RetryableError(f"transport: {e}") from e

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            reset = resp.headers.get("X-RateLimit-Reset")
            if reset:
                log.info(
                    "newsapi: rate-limited (reset=%s); tenacity will back off", reset
                )
            raise _RetryableError(
                f"upstream {resp.status_code}: {resp.text[:200]}"
            )
        if resp.status_code >= 400:
            log.warning(
                "newsapi: non-retryable %s: %s",
                resp.status_code,
                resp.text[:200],
            )
            return {"articles": []}

        return resp.json()
