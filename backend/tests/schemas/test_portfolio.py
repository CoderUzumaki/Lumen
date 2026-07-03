"""DATA-02 acceptance tests: valid + invalid cases per Pydantic field."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioRead,
    PortfolioUpdate,
    PositionCreate,
    PositionRead,
    PositionUpdate,
)
from app.schemas.preferences import UserPreferencesRead, UserPreferencesUpdate
from app.schemas.theme import ThemeCreate, ThemeRead, ThemeUpdate


# --- Ticker ------------------------------------------------------------------


@pytest.mark.parametrize(
    "ticker",
    ["NVDA", "BRK.B", "GOOGL", "BTC-USD", "AAPL", "NSE:RELIANCE", "A", "1INCH"],
)
def test_valid_ticker(ticker: str):
    p = PositionCreate(ticker=ticker)
    assert p.ticker == ticker


@pytest.mark.parametrize(
    "ticker",
    ["nvda", "brk.b", "TOO_LONG_TICKER_SYMBOL_HERE_123", "AAPL AAPL", "AAPL$", ""],
)
def test_invalid_ticker(ticker: str):
    with pytest.raises(ValidationError):
        PositionCreate(ticker=ticker)


# --- Currency ---------------------------------------------------------------


@pytest.mark.parametrize("currency", ["USD", "INR", "EUR", "GBP"])
def test_valid_currency(currency: str):
    p = PositionCreate(ticker="NVDA", currency=currency)
    assert p.currency == currency


@pytest.mark.parametrize("currency", ["usd", "US", "USDT", "u$d", "United"])
def test_invalid_currency(currency: str):
    with pytest.raises(ValidationError):
        PositionCreate(ticker="NVDA", currency=currency)


# --- Position asset_type + defaults -----------------------------------------


def test_position_defaults():
    p = PositionCreate(ticker="NVDA")
    assert p.asset_type == "equity"
    assert p.currency == "USD"
    assert p.quantity is None
    assert p.cost_basis is None


def test_position_invalid_asset_type():
    with pytest.raises(ValidationError):
        PositionCreate(ticker="NVDA", asset_type="futures")  # not in Literal


def test_position_update_partial():
    upd = PositionUpdate(quantity=Decimal("5"))
    assert upd.quantity == Decimal("5")
    assert upd.ticker is None  # unset fields are None


# --- Portfolio create / update / read ---------------------------------------


def test_portfolio_create_minimal():
    p = PortfolioCreate(name="Main")
    assert p.name == "Main"
    assert p.is_active is False


def test_portfolio_create_empty_name_rejected():
    with pytest.raises(ValidationError):
        PortfolioCreate(name="")


def test_portfolio_update_all_optional():
    # empty update is valid — the route layer decides whether to no-op.
    upd = PortfolioUpdate()
    assert upd.name is None
    assert upd.is_active is None


def test_portfolio_read_embeds_positions():
    pos = PositionRead(
        id=uuid4(),
        portfolio_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        ticker="NVDA",
    )
    port = PortfolioRead(
        id=uuid4(),
        user_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        name="Main",
        is_active=True,
        positions=[pos],
    )
    assert len(port.positions) == 1
    assert port.positions[0].ticker == "NVDA"


# --- Theme ------------------------------------------------------------------


@pytest.mark.parametrize("desc", ["AI capex cycle", "abc", "x" * 200])
def test_theme_valid_description(desc: str):
    t = ThemeCreate(description=desc)
    assert t.description == desc


@pytest.mark.parametrize("desc", ["", "ab", "x" * 201])
def test_theme_invalid_description(desc: str):
    with pytest.raises(ValidationError):
        ThemeCreate(description=desc)


@pytest.mark.parametrize("weight", [Decimal("0"), Decimal("0.5"), Decimal("1")])
def test_theme_valid_weight(weight: Decimal):
    t = ThemeCreate(description="valid desc", weight=weight)
    assert t.weight == weight


@pytest.mark.parametrize("weight", [Decimal("-0.01"), Decimal("1.01"), Decimal("2")])
def test_theme_invalid_weight(weight: Decimal):
    with pytest.raises(ValidationError):
        ThemeCreate(description="valid desc", weight=weight)


def test_theme_default_weight():
    t = ThemeCreate(description="valid desc")
    assert t.weight == Decimal("1.0")


def test_theme_update_partial():
    upd = ThemeUpdate(weight=Decimal("0.5"))
    assert upd.weight == Decimal("0.5")
    assert upd.description is None


def test_theme_read_shape():
    t = ThemeRead(
        id=uuid4(),
        user_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        description="AI capex cycle",
        weight=Decimal("0.8"),
        embedding_id="chroma-doc-xyz",
    )
    assert t.embedding_id == "chroma-doc-xyz"


# --- User preferences -------------------------------------------------------


def test_preferences_defaults_via_update():
    upd = UserPreferencesUpdate()
    assert upd.briefing_hour is None
    assert upd.model_tier is None


def test_preferences_valid_update():
    upd = UserPreferencesUpdate(briefing_hour=6, model_tier="fast", display_currency="INR")
    assert upd.briefing_hour == 6
    assert upd.model_tier == "fast"
    assert upd.display_currency == "INR"


@pytest.mark.parametrize("hour", [-1, 24, 999])
def test_preferences_invalid_briefing_hour(hour: int):
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(briefing_hour=hour)


def test_preferences_invalid_model_tier():
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(model_tier="lightning")


def test_preferences_invalid_currency():
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(display_currency="us")  # not 3-letter uppercase


def test_preferences_read_defaults():
    r = UserPreferencesRead(
        user_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert r.briefing_hour == 8
    assert r.briefing_timezone == "UTC"
    assert r.display_currency == "USD"
    assert r.model_tier == "thorough"
