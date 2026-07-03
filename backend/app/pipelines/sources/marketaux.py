"""Marketaux adapter (ING-03).

Free tier: ~100 requests/day. Marketaux enriches each article with an
`entities` list (`symbol`, `type`, `sentiment_score`, …). We copy the
`symbol` values into `NewsItemIn.hints["tickers"]` so the relevance engine
(REL-02) can prefilter without re-running entity extraction.

Endpoint: `https://api.marketaux.com/v1/news/all`
Query params: `filter_entities=true`, `language=en`, `limit=50`,
`published_after=<since ISO8601>`, `api_token=<key>`.

Same never-raise contract as `NewsAPISource`: missing key → warning + [];
transient failure → retry then [] on exhaustion.
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

_ENDPOINT = "https://api.marketaux.com/v1/news/all"


class _RetryableError(Exception):
    """429, 5xx, or transport error → retry."""


class MarketauxSource(BaseSource):
    source_name = "marketaux"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        limit: int = 50,
    ):
        self._api_key = api_key if api_key is not None else Config.MARKETAUX_KEY
        self._http = http_client
        self._own_http = http_client is None
        self._limit = limit

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
            log.warning("marketaux: MARKETAUX_KEY not configured — skipping")
            return []

        params = {
            "filter_entities": "true",
            "language": "en",
            "limit": self._limit,
            "published_after": since.isoformat(),
            "api_token": self._api_key,
        }

        try:
            data = await self._call_with_retry(params)
        except RetryError:
            log.warning("marketaux: exhausted retries; returning empty list")
            return []
        except Exception:  # pragma: no cover — defensive
            log.exception("marketaux: unexpected error; returning empty list")
            return []

        rows = data.get("data") or []
        items: list[NewsItemIn] = []
        for row in rows:
            try:
                items.append(self._to_news_item(row))
            except Exception:
                log.exception("marketaux: could not parse row; skipping")
        return items

    def _to_news_item(self, row: dict[str, Any]) -> NewsItemIn:
        entities = row.get("entities") or []
        # Preserve order + dedup while keeping only strings we can trust.
        tickers: list[str] = []
        seen: set[str] = set()
        for e in entities:
            sym = e.get("symbol") if isinstance(e, dict) else None
            if isinstance(sym, str) and sym and sym not in seen:
                tickers.append(sym)
                seen.add(sym)

        return NewsItemIn(
            source="marketaux",
            source_id=row.get("uuid"),
            url=row["url"],
            title=row["title"],
            body=row.get("description") or row.get("snippet"),
            published_at=row["published_at"],
            raw_payload=row,
            hints={"tickers": tickers} if tickers else {},
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
        raise RetryError(last_attempt=None)  # type: ignore[arg-type]  # pragma: no cover

    async def _one_call(self, params: dict[str, Any]) -> dict[str, Any]:
        http = await self._get_http()
        try:
            resp = await http.get(_ENDPOINT, params=params)
        except httpx.HTTPError as e:
            raise _RetryableError(f"transport: {e}") from e

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise _RetryableError(f"upstream {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            log.warning(
                "marketaux: non-retryable %s: %s",
                resp.status_code,
                resp.text[:200],
            )
            return {"data": []}

        return resp.json()
