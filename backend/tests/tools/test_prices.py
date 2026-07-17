"""IMP-03 acceptance tests for the price-context tool.

Tests are hermetic: `yfinance.Ticker` is patched at `app.tools.prices` so no
real network call is made. Cache directory is redirected to a per-test temp
path so the on-disk cache does not leak between test runs.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.tools import prices as prices_mod
from app.tools.prices import PriceContext, get_recent_price_action


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_history(closes: list[float], end: date | None = None) -> pd.DataFrame:
    """Build a `yfinance`-shaped history frame with the given closes.

    Index is a business-day DatetimeIndex ending on `end` (defaults to today).
    """
    end = end or date.today()
    idx = pd.bdate_range(end=pd.Timestamp(end), periods=len(closes))
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Adj Close": closes,
            "Volume": [1000] * len(closes),
        },
        index=idx,
    )


def _fake_ticker(history_df: pd.DataFrame, currency: str = "USD") -> MagicMock:
    ticker = MagicMock()
    ticker.history.return_value = history_df
    ticker.fast_info = SimpleNamespace(currency=currency)
    return ticker


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Redirect the module-level cache dir to a scratch location per test."""
    cache = tmp_path / "price_cache"
    cache.mkdir()
    monkeypatch.setattr(prices_mod, "_CACHE_DIR", cache)
    return cache


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_happy_path_populates_price_context(cache_dir):
    """yfinance returns a plausible history → PriceContext populated end-to-end."""
    # 40 sessions of 1% daily growth starting at 100 → last close = 100 * 1.01**39
    closes = [round(100.0 * (1.01 ** i), 4) for i in range(40)]
    history = _make_history(closes)

    with patch.object(prices_mod, "yfinance") as yf:
        yf.Ticker.return_value = _fake_ticker(history, currency="USD")
        ctx = get_recent_price_action("aapl")

    assert ctx is not None
    assert isinstance(ctx, PriceContext)
    assert ctx.ticker == "AAPL"
    assert ctx.currency == "USD"
    assert ctx.current == Decimal(str(closes[-1]))
    # 1d ratio = last/prev - 1 ≈ 0.01
    assert ctx.pct_change_1d == pytest.approx((closes[-1] - closes[-2]) / closes[-2])
    assert ctx.pct_change_5d == pytest.approx((closes[-1] - closes[-6]) / closes[-6])
    assert ctx.pct_change_30d == pytest.approx((closes[-1] - closes[-31]) / closes[-31])
    # sanity: ratios, not percentages
    assert 0 < ctx.pct_change_1d < 0.1


def test_ratios_have_known_exact_values(cache_dir):
    """Small hand-crafted series with easy arithmetic keeps the math honest."""
    # Six sessions so pct_change_5d hits index 0 exactly.
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    # yfinance history has today as the last index; today's YTD base = first
    # close on/after Jan 1 of the current year. To keep the test deterministic
    # regardless of what "today" is when the test runs, we make sure the
    # entire history sits inside the current calendar year.
    year = date.today().year
    end = date(year, 6, 30)
    if end > date.today():
        end = date.today()
    history = _make_history(closes, end=end)

    with patch.object(prices_mod, "yfinance") as yf:
        yf.Ticker.return_value = _fake_ticker(history, currency="USD")
        ctx = get_recent_price_action("MSFT")

    assert ctx is not None
    assert ctx.current == Decimal("105.0")
    assert ctx.pct_change_1d == pytest.approx((105.0 - 104.0) / 104.0)
    assert ctx.pct_change_5d == pytest.approx((105.0 - 100.0) / 100.0)
    # Only 6 sessions available so pct_change_30d falls back to earliest close.
    assert ctx.pct_change_30d == pytest.approx((105.0 - 100.0) / 100.0)
    # YTD base is the first close (all bars sit inside the current year).
    assert ctx.pct_change_ytd == pytest.approx((105.0 - 100.0) / 100.0)


def test_cache_hit_avoids_second_yfinance_call(cache_dir):
    """Second same-day call must read from cache and skip yfinance."""
    closes = [100.0, 102.0]
    history = _make_history(closes)

    with patch.object(prices_mod, "yfinance") as yf:
        yf.Ticker.return_value = _fake_ticker(history, currency="USD")

        first = get_recent_price_action("SPY")
        second = get_recent_price_action("SPY")

        assert first is not None
        assert second is not None
        assert first.model_dump() == second.model_dump()
        # First call resolved via yfinance, second via cache → exactly one call.
        assert yf.Ticker.call_count == 1

    # Cache file was actually written to disk.
    expected = cache_dir / f"SPY_{date.today().isoformat()}.json"
    assert expected.exists()
    on_disk = json.loads(expected.read_text(encoding="utf-8"))
    assert on_disk["ticker"] == "SPY"
    # Decimal precision preserved as string.
    assert on_disk["current"] == "102.0"


def test_stale_cache_from_yesterday_is_ignored(cache_dir):
    """A cache file dated yesterday is stale → yfinance is called again."""
    yesterday = date.today() - timedelta(days=1)
    stale = cache_dir / f"NVDA_{yesterday.isoformat()}.json"
    stale.write_text(
        json.dumps(
            {
                "ticker": "NVDA",
                "current": "1.00",  # deliberately absurd — proves we didn't read it
                "pct_change_1d": 0.0,
                "pct_change_5d": 0.0,
                "pct_change_30d": 0.0,
                "pct_change_ytd": 0.0,
                "currency": "USD",
            }
        ),
        encoding="utf-8",
    )

    closes = [200.0, 210.0]
    history = _make_history(closes)

    with patch.object(prices_mod, "yfinance") as yf:
        yf.Ticker.return_value = _fake_ticker(history, currency="USD")
        ctx = get_recent_price_action("NVDA")

    assert ctx is not None
    assert ctx.current == Decimal("210.0")  # fresh data, not the stale 1.00
    # Fresh cache file for today was created and is separate from the stale one.
    fresh = cache_dir / f"NVDA_{date.today().isoformat()}.json"
    assert fresh.exists()
    assert stale.exists()  # stale file left untouched


def test_unknown_ticker_returns_none(cache_dir):
    """yfinance returns an empty history for garbage tickers → None."""
    empty = pd.DataFrame(
        {"Open": [], "High": [], "Low": [], "Close": [], "Adj Close": [], "Volume": []}
    )

    with patch.object(prices_mod, "yfinance") as yf:
        yf.Ticker.return_value = _fake_ticker(empty, currency="USD")
        ctx = get_recent_price_action("ZZZZNOTREAL")

    assert ctx is None
    # No cache file should be written for a failed lookup.
    assert list(cache_dir.iterdir()) == []


def test_yfinance_exception_is_swallowed(cache_dir):
    """A raised network exception must surface as None, not propagate."""
    class BoomTicker:
        def history(self, *_, **__):
            raise RuntimeError("simulated network failure")

        fast_info = SimpleNamespace(currency="USD")

    with patch.object(prices_mod, "yfinance") as yf:
        yf.Ticker.return_value = BoomTicker()
        ctx = get_recent_price_action("AAPL")

    assert ctx is None
    assert list(cache_dir.iterdir()) == []


def test_empty_ticker_returns_none(cache_dir):
    """Guard against empty/whitespace inputs before touching yfinance."""
    with patch.object(prices_mod, "yfinance") as yf:
        assert get_recent_price_action("") is None
        assert get_recent_price_action("   ") is None
        yf.Ticker.assert_not_called()


def test_cache_roundtrip_preserves_decimal_precision(cache_dir):
    """Currency-sensitive values must not lose precision through JSON."""
    closes = [123.456789, 987.654321]
    history = _make_history(closes)

    with patch.object(prices_mod, "yfinance") as yf:
        yf.Ticker.return_value = _fake_ticker(history, currency="EUR")
        first = get_recent_price_action("SAP")
        # Second call reads the on-disk cache and must yield the same Decimal.
        second = get_recent_price_action("SAP")

    assert first is not None and second is not None
    assert first.current == Decimal("987.654321")
    assert second.current == Decimal("987.654321")
    assert first.currency == "EUR"
    assert second.currency == "EUR"
