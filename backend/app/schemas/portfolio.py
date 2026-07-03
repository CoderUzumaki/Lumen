"""Pydantic v2 schemas for portfolios and positions (DATA-02).

Naming:
- `*Create` — request body for POST endpoints (fields the user supplies).
- `*Update` — request body for PUT endpoints (all fields optional).
- `*Read`   — response body (includes DB-generated fields like `id`,
              `created_at`, and — on portfolios — the embedded positions list).

Validation rules per BUILD.md DATA-02:
- Ticker matches `^[A-Z0-9.\\-:]{1,20}$` (upper-cased; dots, hyphens, and
  colons allowed for BRK.B, futures symbols, and exchange-prefixed tickers).
- Currency is ISO 4217 uppercase (three letters).
- Weight is in [0.0, 1.0] — enforced here on themes; portfolios don't carry
  a weight but positions carry quantity and cost_basis with no range constraint.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


AssetType = Literal["equity", "etf", "crypto", "bond", "other"]

TICKER_PATTERN = r"^[A-Z0-9.\-:]{1,20}$"
CURRENCY_PATTERN = r"^[A-Z]{3}$"


# --- Position ---------------------------------------------------------------


class PositionBase(BaseModel):
    """Fields shared by all Position request/response shapes."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(pattern=TICKER_PATTERN, description="Uppercased symbol, e.g. NVDA, BRK.B.")
    asset_type: AssetType = "equity"
    quantity: Decimal | None = None
    cost_basis: Decimal | None = None
    currency: str = Field(default="USD", pattern=CURRENCY_PATTERN)
    exchange: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=2000)


class PositionCreate(PositionBase):
    """Body for `POST /api/portfolios/{id}/positions`."""


class PositionUpdate(BaseModel):
    """Body for `PUT /api/positions/{position_id}`. Every field optional."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str | None = Field(default=None, pattern=TICKER_PATTERN)
    asset_type: AssetType | None = None
    quantity: Decimal | None = None
    cost_basis: Decimal | None = None
    currency: str | None = Field(default=None, pattern=CURRENCY_PATTERN)
    exchange: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=2000)


class PositionRead(PositionBase):
    """Response body for a single position."""

    id: UUID
    portfolio_id: UUID
    created_at: datetime


# --- Portfolio --------------------------------------------------------------


class PortfolioBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(min_length=1, max_length=120)
    is_active: bool = False


class PortfolioCreate(PortfolioBase):
    """Body for `POST /api/portfolios`."""


class PortfolioUpdate(BaseModel):
    """Body for `PUT /api/portfolios/{id}`. Every field optional."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None


class PortfolioRead(PortfolioBase):
    """Response body for a portfolio. Embeds its positions."""

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    positions: list[PositionRead] = Field(default_factory=list)
