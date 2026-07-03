"""ING-06 acceptance: fixture RSS XML yields correct NewsItemIn objects."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx

from app.pipelines.sources.rss import RSSSource


RSS_FIXTURE_1 = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed 1</title>
    <link>https://feed1.example</link>
    <description>test</description>
    <item>
      <title>Fed hikes 25bps</title>
      <link>https://feed1.example/fed-hike</link>
      <description>Rates up by a quarter point.</description>
      <pubDate>Wed, 03 Jul 2026 12:00:00 +0000</pubDate>
      <guid>feed1-fed-hike</guid>
    </item>
    <item>
      <title>Oil to $100</title>
      <link>https://feed1.example/oil-100</link>
      <description>Brent surges.</description>
      <pubDate>Wed, 03 Jul 2026 13:00:00 +0000</pubDate>
      <guid>feed1-oil-100</guid>
    </item>
    <item>
      <title>Stale - from 2020</title>
      <link>https://feed1.example/stale</link>
      <description>Historical item, should be filtered by since.</description>
      <pubDate>Wed, 01 Jan 2020 00:00:00 +0000</pubDate>
      <guid>feed1-stale</guid>
    </item>
  </channel>
</rss>"""

RSS_FIXTURE_2 = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed 2</title>
    <link>https://feed2.example</link>
    <description>test</description>
    <item>
      <title>NVDA reports Q4</title>
      <link>https://feed2.example/nvda-q4</link>
      <description>Revenue beats estimates.</description>
      <pubDate>Wed, 03 Jul 2026 14:00:00 +0000</pubDate>
      <guid>feed2-nvda-q4</guid>
    </item>
    <item>
      <title>Fed hikes 25bps</title>
      <link>https://feed1.example/fed-hike</link>
      <description>Same URL as feed1 item; should be deduped.</description>
      <pubDate>Wed, 03 Jul 2026 12:15:00 +0000</pubDate>
      <guid>feed2-dup-fed-hike</guid>
    </item>
  </channel>
</rss>"""

MALFORMED_ITEM_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Broken</title>
    <link>https://broken.example</link>
    <description>test</description>
    <item>
      <!-- no link -->
      <title>orphan title</title>
      <pubDate>Wed, 03 Jul 2026 12:00:00 +0000</pubDate>
    </item>
    <item>
      <title>good one</title>
      <link>https://broken.example/good</link>
      <description>fine</description>
      <pubDate>Wed, 03 Jul 2026 13:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""


def _mk_http(url_to_response: dict[str, httpx.Response | Exception]):
    calls: list[str] = []

    async def get(url, **kwargs):
        calls.append(url)
        r = url_to_response.get(url)
        if r is None:
            return httpx.Response(404, text=f"no route for {url}")
        if isinstance(r, Exception):
            raise r
        return r

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=get)
    client.aclose = AsyncMock()
    return client, calls


async def test_fixture_yields_correct_news_items():
    http, calls = _mk_http(
        {"https://feed1.example/rss": httpx.Response(200, content=RSS_FIXTURE_1)}
    )
    src = RSSSource(
        feeds=["https://feed1.example/rss"],
        http_client=http,
    )
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    items = await src.fetch(since)

    assert calls == ["https://feed1.example/rss"]
    assert len(items) == 2  # stale item filtered out
    urls = {str(i.url) for i in items}
    assert urls == {
        "https://feed1.example/fed-hike",
        "https://feed1.example/oil-100",
    }
    fed = next(i for i in items if "fed-hike" in str(i.url))
    assert fed.source == "rss"
    assert fed.title == "Fed hikes 25bps"
    assert fed.body == "Rates up by a quarter point."
    assert fed.source_id == "feed1-fed-hike"
    assert fed.published_at == datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


async def test_url_hash_dedup_across_feeds():
    http, _ = _mk_http(
        {
            "https://feed1.example/rss": httpx.Response(200, content=RSS_FIXTURE_1),
            "https://feed2.example/rss": httpx.Response(200, content=RSS_FIXTURE_2),
        }
    )
    src = RSSSource(
        feeds=["https://feed1.example/rss", "https://feed2.example/rss"],
        http_client=http,
    )
    items = await src.fetch(datetime(2026, 1, 1, tzinfo=timezone.utc))
    urls = [str(i.url) for i in items]

    assert len(items) == 3
    # feed1's fed-hike wins (first seen); feed2's dup with the same URL is dropped.
    assert urls.count("https://feed1.example/fed-hike") == 1
    assert "https://feed2.example/nvda-q4" in urls
    assert "https://feed1.example/oil-100" in urls


async def test_empty_feeds_list_returns_empty():
    http, calls = _mk_http({})
    src = RSSSource(feeds=[], http_client=http)
    items = await src.fetch(datetime.now(timezone.utc))
    assert items == []
    assert calls == []


async def test_feed_error_is_skipped_not_raised():
    http, _ = _mk_http(
        {
            "https://feed1.example/rss": httpx.Response(200, content=RSS_FIXTURE_1),
            "https://broken.example/rss": httpx.ConnectError("boom"),
        }
    )
    src = RSSSource(
        feeds=["https://broken.example/rss", "https://feed1.example/rss"],
        http_client=http,
    )
    items = await src.fetch(datetime(2026, 1, 1, tzinfo=timezone.utc))

    # broken feed swallowed; feed1's 2 items still land.
    assert len(items) == 2


async def test_malformed_entry_dropped_other_entries_survive():
    http, _ = _mk_http(
        {"https://broken.example/rss": httpx.Response(200, content=MALFORMED_ITEM_RSS)}
    )
    src = RSSSource(feeds=["https://broken.example/rss"], http_client=http)
    items = await src.fetch(datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert len(items) == 1
    assert str(items[0].url) == "https://broken.example/good"


async def test_non_200_response_yields_no_items():
    http, _ = _mk_http({"https://feed1.example/rss": httpx.Response(500)})
    src = RSSSource(feeds=["https://feed1.example/rss"], http_client=http)
    items = await src.fetch(datetime.now(timezone.utc))
    assert items == []
