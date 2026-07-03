"""SEC EDGAR adapter (ING-05).

For each ticker the caller passes, this adapter:
1. Resolves the CIK via a bundled `ticker_to_cik.json` map (top US tickers).
2. Fetches `https://data.sec.gov/submissions/CIK<10-digit>.json` and reads
   the `recent` filing arrays.
3. Emits one `NewsItemIn` per 8-K / 10-K / 10-Q filing newer than `since`,
   with `title="<ticker> filed <form> on <date>"`, `source_id=accession`,
   and `body=` the first 4000 chars of the parsed primary document (best
   effort — selectolax).

SEC fair-use policy requires a `User-Agent: <Company> <contact-email>`
header on every request; the adapter reads it from `Config.EDGAR_USER_AGENT`.

Never raises: missing CIK / bad UA / transport failure all log-and-skip.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from selectolax.parser import HTMLParser
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

_TICKER_TO_CIK_PATH = Path(__file__).parent / "data" / "ticker_to_cik.json"
_INTERESTING_FORMS = frozenset({"8-K", "10-K", "10-Q"})
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
_FILING_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/"
)
_BODY_MAX_CHARS = 4000


class _RetryableError(Exception):
    pass


def _load_ticker_to_cik() -> dict[str, str]:
    with _TICKER_TO_CIK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


class EDGARSource(BaseSource):
    source_name = "edgar"

    _ticker_to_cik = _load_ticker_to_cik()

    def __init__(
        self,
        *,
        tickers: list[str],
        http_client: httpx.AsyncClient | None = None,
        max_filings_per_ticker: int = 5,
    ):
        self._tickers = [t.upper() for t in tickers]
        self._http = http_client
        self._own_http = http_client is None
        self._max_filings = max_filings_per_ticker

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            ua = Config.EDGAR_USER_AGENT
            self._http = httpx.AsyncClient(
                timeout=30.0, headers={"User-Agent": ua, "Accept-Encoding": "gzip"}
            )
        return self._http

    async def aclose(self) -> None:
        if self._http is not None and self._own_http:
            await self._http.aclose()
            self._http = None

    async def fetch(self, since: datetime) -> list[NewsItemIn]:
        since_utc = since.astimezone(timezone.utc)
        items: list[NewsItemIn] = []
        for ticker in self._tickers:
            cik = self._ticker_to_cik.get(ticker)
            if not cik:
                log.info("edgar: no CIK for %s; skipping", ticker)
                continue
            try:
                filings = await self._recent_filings(ticker, cik, since_utc)
            except RetryError:
                log.warning("edgar: exhausted retries for %s; skipping", ticker)
                continue
            except Exception:
                log.exception("edgar: %s submissions fetch failed; skipping", ticker)
                continue
            for f in filings[: self._max_filings]:
                try:
                    body = await self._fetch_body(cik, f["accession"], f["primary_doc"])
                except Exception:
                    log.exception(
                        "edgar: body fetch failed for %s / %s; leaving body None",
                        ticker,
                        f["accession"],
                    )
                    body = None
                items.append(self._to_news_item(ticker, cik, f, body))
        return items

    # ----- internals ---------------------------------------------------------

    async def _recent_filings(
        self, ticker: str, cik: str, since_utc: datetime
    ) -> list[dict[str, str]]:
        data = await self._call_with_retry(_SUBMISSIONS_URL.format(cik10=cik))
        recent = ((data.get("filings") or {}).get("recent")) or {}
        acc = recent.get("accessionNumber") or []
        form = recent.get("form") or []
        filing_date = recent.get("filingDate") or []
        primary_doc = recent.get("primaryDocument") or []

        out: list[dict[str, str]] = []
        for i, form_type in enumerate(form):
            if form_type not in _INTERESTING_FORMS:
                continue
            try:
                fd = date.fromisoformat(filing_date[i])
            except (ValueError, IndexError):
                continue
            fd_utc = datetime(fd.year, fd.month, fd.day, tzinfo=timezone.utc)
            if fd_utc < since_utc:
                continue
            try:
                out.append(
                    {
                        "accession": acc[i],
                        "form": form_type,
                        "date": filing_date[i],
                        "primary_doc": primary_doc[i],
                    }
                )
            except IndexError:
                continue
        return out

    async def _fetch_body(
        self, cik: str, accession: str, primary_doc: str
    ) -> str | None:
        # Accession dashed form: 0000320193-24-000123 → 000032019324000123.
        accession_nd = accession.replace("-", "")
        cik_int = int(cik)
        url = _FILING_INDEX_URL.format(cik_int=cik_int, accession_no_dashes=accession_nd)
        url = f"{url}{primary_doc}"

        http = await self._get_http()
        try:
            resp = await http.get(url)
        except httpx.HTTPError as e:
            log.info("edgar: transport error fetching %s: %s", url, e)
            return None

        if resp.status_code != 200:
            return None

        try:
            tree = HTMLParser(resp.text)
            text = tree.text(separator=" ", strip=True) or ""
        except Exception:
            return None
        # First 4000 chars of the narrative section (best effort — no attempt
        # to skip cover pages or exhibits here; downstream cleaning can go
        # deeper).
        return text[:_BODY_MAX_CHARS] or None

    def _to_news_item(
        self,
        ticker: str,
        cik: str,
        filing: dict[str, str],
        body: str | None,
    ) -> NewsItemIn:
        accession = filing["accession"]
        form_type = filing["form"]
        filing_date_str = filing["date"]
        accession_nd = accession.replace("-", "")
        cik_int = int(cik)
        url = f"{_FILING_INDEX_URL.format(cik_int=cik_int, accession_no_dashes=accession_nd)}{filing['primary_doc']}"

        published_at = datetime.fromisoformat(filing_date_str).replace(
            tzinfo=timezone.utc
        )
        return NewsItemIn(
            source="edgar",
            source_id=accession,
            url=url,
            title=f"{ticker} filed {form_type} on {filing_date_str}",
            body=body,
            published_at=published_at,
            raw_payload=filing,
            hints={"tickers": [ticker], "form": form_type, "cik": cik},
        )

    async def _call_with_retry(self, url: str) -> dict[str, Any]:
        retrying = AsyncRetrying(
            reraise=True,
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8.0),
            retry=retry_if_exception_type(_RetryableError),
        )
        async for attempt in retrying:
            with attempt:
                return await self._one_call(url)
        raise RetryError(last_attempt=None)  # type: ignore[arg-type]  # pragma: no cover

    async def _one_call(self, url: str) -> dict[str, Any]:
        http = await self._get_http()
        try:
            resp = await http.get(url)
        except httpx.HTTPError as e:
            raise _RetryableError(f"transport: {e}") from e

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise _RetryableError(f"upstream {resp.status_code}")
        if resp.status_code >= 400:
            log.warning("edgar: non-retryable %s on %s", resp.status_code, url)
            return {}
        return resp.json()
