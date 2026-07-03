"""ING-05 acceptance for the EDGAR adapter."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest

from app.pipelines.sources.edgar import EDGARSource


AAPL_SUBMISSIONS = {
    "cik": "320193",
    "name": "Apple Inc.",
    "tickers": ["AAPL"],
    "filings": {
        "recent": {
            "accessionNumber": [
                "0000320193-25-000001",
                "0000320193-24-000123",
                "0000320193-24-000100",
                "0000320193-24-000090",
            ],
            "form": ["10-K", "8-K", "10-Q", "S-4"],
            "filingDate": [
                "2026-01-15",
                "2025-12-20",
                "2025-10-30",
                "2025-09-15",
            ],
            "primaryDocument": [
                "aapl-20260115.htm",
                "aapl-20251220-8k.htm",
                "aapl-20251030-10q.htm",
                "aapl-20250915-s4.htm",
            ],
        }
    },
}

SAMPLE_FILING_HTML = (
    "<html><body>"
    "<h1>Apple Inc. — 10-K</h1>"
    "<p>Fiscal year 2026 results discussion.</p>"
    "<p>Revenue grew 8% year over year, driven by services.</p>"
    "</body></html>"
)


def _mk_http(routes: dict[str, list]):
    """Fake AsyncClient that dispatches by exact URL match on GET."""
    calls: list[str] = []

    async def get(url, **kwargs):
        calls.append(url)
        queue = routes.get(url)
        if queue is None:
            # unknown URL: return 404
            return httpx.Response(404, text=f"no route for {url}")
        r = queue.pop(0) if queue else httpx.Response(404, text="empty queue")
        if isinstance(r, Exception):
            raise r
        return r

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=get)
    client.aclose = AsyncMock()
    return client, calls


def _submissions_url(cik10: str) -> str:
    return f"https://data.sec.gov/submissions/CIK{cik10}.json"


def _filing_doc_url(cik_int: int, accession: str, doc: str) -> str:
    accession_nd = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nd}/{doc}"


async def test_last_three_aapl_filings_have_parsed_bodies():
    """Acceptance: AAPL adapter returns its recent interesting filings with parsed bodies."""
    aapl_cik = "0000320193"
    aapl_cik_int = 320193

    submissions_response = httpx.Response(200, json=AAPL_SUBMISSIONS)
    filing_html_response = httpx.Response(200, text=SAMPLE_FILING_HTML)

    filings = AAPL_SUBMISSIONS["filings"]["recent"]
    routes = {_submissions_url(aapl_cik): [submissions_response]}
    for i, form in enumerate(filings["form"]):
        if form not in ("8-K", "10-K", "10-Q"):
            continue
        url = _filing_doc_url(
            aapl_cik_int, filings["accessionNumber"][i], filings["primaryDocument"][i]
        )
        routes[url] = [filing_html_response]

    http, _ = _mk_http(routes)
    src = EDGARSource(tickers=["AAPL"], http_client=http, max_filings_per_ticker=3)

    items = await src.fetch(since=datetime(2025, 1, 1, tzinfo=timezone.utc))

    assert len(items) == 3
    # forms should be the three interesting ones, S-4 excluded.
    forms = [i.raw_payload["form"] for i in items]
    assert set(forms) == {"10-K", "8-K", "10-Q"}
    for i in items:
        assert i.source == "edgar"
        assert i.source_id.startswith("0000320193-")
        assert i.title.startswith("AAPL filed ")
        assert i.body is not None
        assert "Apple Inc." in i.body or "Revenue grew" in i.body
        assert i.hints["tickers"] == ["AAPL"]
        assert i.hints["cik"] == aapl_cik


async def test_unknown_ticker_is_skipped_not_fatal():
    http, calls = _mk_http({})
    src = EDGARSource(tickers=["XXXXX-UNKNOWN"], http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert items == []
    # No HTTP calls made because the ticker didn't resolve.
    assert calls == []


async def test_since_filter_drops_older_filings():
    aapl_cik = "0000320193"
    aapl_cik_int = 320193

    submissions_response = httpx.Response(200, json=AAPL_SUBMISSIONS)
    filing_html_response = httpx.Response(200, text=SAMPLE_FILING_HTML)

    filings = AAPL_SUBMISSIONS["filings"]["recent"]
    routes = {_submissions_url(aapl_cik): [submissions_response]}
    for i, form in enumerate(filings["form"]):
        if form not in ("8-K", "10-K", "10-Q"):
            continue
        url = _filing_doc_url(
            aapl_cik_int, filings["accessionNumber"][i], filings["primaryDocument"][i]
        )
        routes[url] = [filing_html_response]

    http, _ = _mk_http(routes)
    src = EDGARSource(tickers=["AAPL"], http_client=http)

    # Since Jan 1 2026 — only the 10-K (2026-01-15) is newer.
    items = await src.fetch(since=datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert len(items) == 1
    assert items[0].raw_payload["form"] == "10-K"


async def test_body_fetch_failure_leaves_body_none():
    aapl_cik = "0000320193"
    aapl_cik_int = 320193

    submissions_response = httpx.Response(200, json=AAPL_SUBMISSIONS)
    filings = AAPL_SUBMISSIONS["filings"]["recent"]
    routes = {_submissions_url(aapl_cik): [submissions_response]}
    # Make every filing doc 500 → body will be None, but the item is still emitted.
    for i, form in enumerate(filings["form"]):
        if form not in ("8-K", "10-K", "10-Q"):
            continue
        url = _filing_doc_url(
            aapl_cik_int, filings["accessionNumber"][i], filings["primaryDocument"][i]
        )
        routes[url] = [httpx.Response(500, text="bad")]

    http, _ = _mk_http(routes)
    src = EDGARSource(tickers=["AAPL"], http_client=http)

    items = await src.fetch(since=datetime(2025, 1, 1, tzinfo=timezone.utc))

    assert len(items) == 3
    assert all(i.body is None for i in items)


async def test_submissions_500_causes_ticker_skip_not_raise():
    aapl_cik = "0000320193"
    routes = {
        _submissions_url(aapl_cik): [
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(500),
        ]
    }
    http, _ = _mk_http(routes)
    src = EDGARSource(tickers=["AAPL"], http_client=http)

    items = await src.fetch(since=datetime.now(timezone.utc))

    assert items == []


@pytest.mark.integration
async def test_live_aapl_last_three_filings():
    """Live probe against SEC EDGAR. Requires network + EDGAR_USER_AGENT."""
    src = EDGARSource(tickers=["AAPL"], max_filings_per_ticker=3)
    try:
        items = await src.fetch(since=datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert len(items) >= 1, "expected at least one recent AAPL filing"
        assert all(i.title.startswith("AAPL filed ") for i in items)
    finally:
        await src.aclose()
