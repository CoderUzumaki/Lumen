"""Recent price action tool for the impact analyst (IMP-03).

Thin wrapper around `yfinance.Ticker(...).history(...)` that returns the last
close plus 1d / 5d / 30d / YTD returns, packaged as a `PriceContext`. The
result is cached to disk under `backend/price_cache/{TICKER}_{date}.json` and
the cache is stale as soon as the calendar day rolls over — a fresh session
the next morning refetches.

Design notes:
- `yfinance` is imported at module import time; if it isn't installed the
  ImportError propagates so the caller can fail fast (per BUILD.md IMP-03).
- Every runtime failure (network error, unknown ticker, empty history) is
  swallowed and surfaces as ``None`` — the impact agent must be robust when a
  ticker is missing, not crash on it.
- Percentages are ratios, not percentages (0.05 == +5%).
- ``pct_change_Nd`` uses the close from N trading sessions before the latest
  available bar. If fewer than N sessions are available the earliest close
  is used and a warning is logged.
- ``pct_change_ytd`` uses the first available close on/after Jan 1 of the
  current calendar year.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import yfinance  # noqa: F401 — import at top so missing dep fails fast
from pydantic import BaseModel

log = logging.getLogger(__name__)

# backend/app/tools/prices.py -> parents[2] == backend/
_CACHE_DIR = Path(__file__).resolve().parents[2] / "price_cache"


class PriceContext(BaseModel):
    """Compact snapshot of recent price action for a single ticker."""

    ticker: str
    current: Decimal
    pct_change_1d: float
    pct_change_5d: float
    pct_change_30d: float
    pct_change_ytd: float
    currency: str


def _cache_path(ticker: str, today: date) -> Path:
    return _CACHE_DIR / f"{ticker.upper()}_{today.isoformat()}.json"


def _read_cache(path: Path) -> PriceContext | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # missing / unreadable / bad JSON
        log.debug("price cache read miss for %s: %s", path.name, exc)
        return None
    try:
        return PriceContext(
            ticker=raw["ticker"],
            current=Decimal(raw["current"]),
            pct_change_1d=float(raw["pct_change_1d"]),
            pct_change_5d=float(raw["pct_change_5d"]),
            pct_change_30d=float(raw["pct_change_30d"]),
            pct_change_ytd=float(raw["pct_change_ytd"]),
            currency=raw.get("currency", "USD"),
        )
    except (KeyError, ValueError, TypeError) as exc:
        log.warning("price cache %s is malformed, ignoring: %s", path.name, exc)
        return None


def _write_cache(path: Path, ctx: PriceContext) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ticker": ctx.ticker,
            "current": str(ctx.current),  # preserve Decimal precision
            "pct_change_1d": ctx.pct_change_1d,
            "pct_change_5d": ctx.pct_change_5d,
            "pct_change_30d": ctx.pct_change_30d,
            "pct_change_ytd": ctx.pct_change_ytd,
            "currency": ctx.currency,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError as exc:  # cache is best-effort; never fail the tool for this
        log.warning("failed to write price cache %s: %s", path.name, exc)


def _pct_change_sessions(closes: list[float], n: int, ticker: str) -> float:
    """Return the fractional change between the latest close and the close N
    trading sessions earlier. Uses the earliest available close when the series
    is shorter than N+1 samples.
    """
    if not closes:
        return 0.0
    last = closes[-1]
    if len(closes) > n:
        base = closes[-(n + 1)]
    else:
        log.warning(
            "price history for %s has only %d sessions (needed %d for pct_change_%dd); "
            "falling back to earliest close",
            ticker,
            len(closes),
            n + 1,
            n,
        )
        base = closes[0]
    if base == 0:
        return 0.0
    return (last - base) / base


def _pct_change_ytd(closes: pd.Series, today: date, ticker: str) -> float:
    """First close on/after Jan 1 of the current year → latest close."""
    if closes.empty:
        return 0.0
    year_start = pd.Timestamp(date(today.year, 1, 1))
    # Normalize the index to timezone-naive Timestamps so the comparison is safe
    # regardless of whether yfinance returned tz-aware bars.
    idx = closes.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    ytd_mask = idx >= year_start
    if not bool(ytd_mask.any()):
        log.warning(
            "no YTD price history for %s (earliest bar %s)", ticker, idx.min()
        )
        base = float(closes.iloc[0])
    else:
        base = float(closes[ytd_mask].iloc[0])
    last = float(closes.iloc[-1])
    if base == 0:
        return 0.0
    return (last - base) / base


def _fetch_from_yfinance(ticker: str) -> PriceContext | None:
    """Pull ~1y of history from yfinance and compute the ratios.

    Any exception, empty response, or malformed frame collapses to ``None``.
    """
    upper = ticker.upper()
    try:
        t = yfinance.Ticker(upper)
        # 1y always covers YTD (even on Jan 2) and 30 trading days comfortably.
        history = t.history(period="1y")
    except Exception as exc:  # noqa: BLE001 — yfinance can raise many types
        log.warning("yfinance history() failed for %s: %s", upper, exc)
        return None

    if history is None or getattr(history, "empty", True):
        log.info("yfinance returned no history for %s", upper)
        return None
    if "Close" not in history.columns:
        log.warning("yfinance frame for %s is missing Close column", upper)
        return None

    close_series = history["Close"].dropna()
    if close_series.empty:
        log.info("yfinance history for %s has no non-null closes", upper)
        return None

    closes = [float(c) for c in close_series.tolist()]
    latest = closes[-1]

    # Currency is best-effort — many providers omit it and we don't want a
    # single missing field to nuke the whole call.
    currency = "USD"
    try:
        fast_info = getattr(t, "fast_info", None)
        if fast_info is not None:
            # fast_info supports both attribute and dict-style access depending
            # on the yfinance version.
            candidate = None
            if hasattr(fast_info, "currency"):
                candidate = fast_info.currency
            if candidate is None:
                try:
                    candidate = fast_info["currency"]  # type: ignore[index]
                except (KeyError, TypeError):
                    candidate = None
            if candidate:
                currency = str(candidate).upper()
    except Exception as exc:  # noqa: BLE001 — currency is not worth failing over
        log.debug("could not read currency for %s: %s", upper, exc)

    today = date.today()
    try:
        return PriceContext(
            ticker=upper,
            current=Decimal(str(latest)),
            pct_change_1d=_pct_change_sessions(closes, 1, upper),
            pct_change_5d=_pct_change_sessions(closes, 5, upper),
            pct_change_30d=_pct_change_sessions(closes, 30, upper),
            pct_change_ytd=_pct_change_ytd(close_series, today, upper),
            currency=currency,
        )
    except Exception as exc:  # noqa: BLE001 — belt-and-suspenders
        log.warning("failed to assemble PriceContext for %s: %s", upper, exc)
        return None


def get_recent_price_action(
    ticker: str, lookback_days: int = 30
) -> PriceContext | None:
    """Return recent price action for ``ticker``.

    The ``lookback_days`` argument is part of the impact-agent contract
    (BUILD.md IMP-03) but the tool always fetches ~1y of history so that
    every ratio, including YTD, can be computed off one request. The
    parameter is retained for future use and to keep the callable signature
    stable.
    """
    del lookback_days  # accepted for API compatibility; not currently needed

    if not ticker or not ticker.strip():
        log.warning("get_recent_price_action called with empty ticker")
        return None

    normalized = ticker.strip().upper()
    today = date.today()
    path = _cache_path(normalized, today)

    cached = _read_cache(path)
    if cached is not None:
        return cached

    ctx = _fetch_from_yfinance(normalized)
    if ctx is None:
        return None

    _write_cache(path, ctx)
    return ctx
