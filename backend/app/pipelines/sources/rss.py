"""RSS adapter (ING-06).

Parses a caller-provided list of RSS/Atom feed URLs (defaulting to
`Config.RSS_FEEDS`). Each feed is fetched via httpx (so tests can mock the
HTTP layer) then handed to `feedparser` in a thread — feedparser itself is
synchronous.

Deduplication: items are de-duped by URL hash before yielding so a single
`fetch()` call never returns two rows with the same URL. This is different
from the DB-level `news_items.url_hash` UNIQUE constraint (ING-01), which
protects the persistence layer — this pass keeps the per-source stream tidy.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from time import struct_time

import feedparser
import httpx

from app.pipelines.sources.base import BaseSource
from app.schemas.news import NewsItemIn
from app.utils.config import Config

log = logging.getLogger(__name__)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _parse_time(t: struct_time | None) -> datetime | None:
    if t is None:
        return None
    try:
        # feedparser fills 9-tuples in UTC.
        return datetime(*t[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


class RSSSource(BaseSource):
    source_name = "rss"

    def __init__(
        self,
        *,
        feeds: list[str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        # None → read Config.RSS_FEEDS at construction time. Explicit empty list
        # is honored — no feeds fetched.
        self._feeds: list[str] = list(Config.RSS_FEEDS) if feeds is None else list(feeds)
        self._http = http_client
        self._own_http = http_client is None

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "Lumen RSS reader (contact@example.com)"},
                follow_redirects=True,
            )
        return self._http

    async def aclose(self) -> None:
        if self._http is not None and self._own_http:
            await self._http.aclose()
            self._http = None

    async def fetch(self, since: datetime) -> list[NewsItemIn]:
        since_utc = since.astimezone(timezone.utc)
        items: list[NewsItemIn] = []
        seen_hashes: set[str] = set()

        for feed_url in self._feeds:
            try:
                feed_items = await self._fetch_feed(feed_url, since_utc)
            except Exception:
                log.exception("rss: feed %s failed; skipping", feed_url)
                continue
            for item in feed_items:
                h = _url_hash(str(item.url))
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)
                items.append(item)
        return items

    async def _fetch_feed(
        self, feed_url: str, since_utc: datetime
    ) -> list[NewsItemIn]:
        http = await self._get_http()
        try:
            resp = await http.get(feed_url)
        except httpx.HTTPError as e:
            log.info("rss: transport error on %s: %s", feed_url, e)
            return []

        if resp.status_code != 200:
            log.info("rss: %s returned %s", feed_url, resp.status_code)
            return []

        parsed = await asyncio.to_thread(feedparser.parse, resp.content)
        if parsed.bozo:
            # feedparser sets bozo=1 for malformed feeds. Keep whatever entries
            # it managed to extract; log the reason at debug.
            log.debug("rss: %s parsed with warnings: %s", feed_url, parsed.bozo_exception)

        return list(self._entries_to_items(parsed.entries, since_utc))

    def _entries_to_items(self, entries, since_utc: datetime):
        for entry in entries:
            link = (entry.get("link") or "").strip()
            if not link:
                continue
            title = (entry.get("title") or "").strip()
            if not title:
                continue

            published = _parse_time(entry.get("published_parsed")) or _parse_time(
                entry.get("updated_parsed")
            )
            if published is None or published < since_utc:
                continue

            body = entry.get("summary") or entry.get("description")

            try:
                yield NewsItemIn(
                    source="rss",
                    source_id=entry.get("id") or None,
                    url=link,
                    title=title,
                    body=body,
                    published_at=published,
                    raw_payload=dict(entry),
                    hints={},
                )
            except Exception:
                # Invalid URL / schema violation on a single item shouldn't kill
                # the whole feed.
                log.exception("rss: dropping malformed entry from feed")
                continue
