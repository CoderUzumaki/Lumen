"""GDELT DOC 2.0 adapter (ING-04).

No API key required — GDELT is a public research project. Response has URL +
title + domain + `seendate` (in `YYYYMMDDTHHMMSSZ` format, no separators). No
body content is returned; `NewsItemIn.body` stays `None` — later stages fetch
the article page separately if needed.

Rate limit: soft, ~1 req/sec. Class-level `asyncio.Semaphore(1)` serializes
all calls across instances of this adapter, and a minimum inter-request
sleep keeps us under the limit even under bursts.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
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

log = logging.getLogger(__name__)

_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
_DEFAULT_QUERY = (
    '(finance OR markets OR stocks OR "Federal Reserve") sourcelang:english'
)
_MIN_INTERVAL_S = 1.0  # 1 req/sec ceiling


class _RetryableError(Exception):
    pass


class GDELTSource(BaseSource):
    source_name = "gdelt"

    # Process-wide serialization. All instances share this — GDELT rate-limits
    # per source IP, so one queue is enough.
    _semaphore: asyncio.Semaphore = asyncio.Semaphore(1)
    _last_call_ts: float = 0.0

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
        query: str = _DEFAULT_QUERY,
        maxrecords: int = 250,
    ):
        self._http = http_client
        self._own_http = http_client is None
        self._query = query
        self._maxrecords = maxrecords

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def aclose(self) -> None:
        if self._http is not None and self._own_http:
            await self._http.aclose()
            self._http = None

    async def fetch(self, since: datetime) -> list[NewsItemIn]:
        # `since` is enforced client-side after we fetch — GDELT's `startdatetime`
        # param uses the same YYYYMMDDHHMMSS shape as `seendate`. Pass it too so
        # the server does the filtering when possible.
        since_utc = since.astimezone(timezone.utc)
        params = {
            "query": self._query,
            "mode": "ArtList",
            "format": "JSON",
            "sort": "DateDesc",
            "maxrecords": self._maxrecords,
            "startdatetime": since_utc.strftime("%Y%m%d%H%M%S"),
        }

        try:
            data = await self._call_with_retry(params)
        except RetryError:
            log.warning("gdelt: exhausted retries; returning empty list")
            return []
        except Exception:  # pragma: no cover
            log.exception("gdelt: unexpected error; returning empty list")
            return []

        articles = data.get("articles") or []
        items: list[NewsItemIn] = []
        for a in articles:
            try:
                item = self._to_news_item(a)
            except Exception:
                log.exception("gdelt: could not parse article; skipping")
                continue
            if item.published_at < since_utc:
                continue  # server-side filter is best-effort; enforce here too
            items.append(item)
        return items

    def _to_news_item(self, article: dict[str, Any]) -> NewsItemIn:
        seendate = article["seendate"]  # "YYYYMMDDTHHMMSSZ"
        published_at = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc
        )
        return NewsItemIn(
            source="gdelt",
            source_id=None,  # GDELT has no stable id
            url=article["url"],
            title=article["title"],
            body=None,
            published_at=published_at,
            raw_payload=article,
            hints={"domain": article["domain"]} if article.get("domain") else {},
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
        async with GDELTSource._semaphore:
            # Enforce the minimum interval across instances.
            elapsed = time.monotonic() - GDELTSource._last_call_ts
            if elapsed < _MIN_INTERVAL_S:
                await asyncio.sleep(_MIN_INTERVAL_S - elapsed)

            http = await self._get_http()
            try:
                resp = await http.get(_ENDPOINT, params=params)
            except httpx.HTTPError as e:
                raise _RetryableError(f"transport: {e}") from e
            finally:
                GDELTSource._last_call_ts = time.monotonic()

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise _RetryableError(f"upstream {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            log.warning(
                "gdelt: non-retryable %s: %s", resp.status_code, resp.text[:200]
            )
            return {"articles": []}

        # GDELT sometimes returns JSON with a UTF-8 BOM. httpx handles it via
        # `response.json()` after 0.27 (bomb-free), but text-mode responses
        # can still trip on it if the server sets a weird content-type. Fall
        # back to text→strip→loads for that case.
        try:
            return resp.json()
        except ValueError:
            import json as _json

            text = resp.text.lstrip("﻿")
            try:
                return _json.loads(text)
            except _json.JSONDecodeError:
                return {"articles": []}
