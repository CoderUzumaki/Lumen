"""`positions` — a ticker held in a portfolio.

Per DATA-01: has `created_at` but no `updated_at`. Unique on
(portfolio_id, ticker, exchange). FK to portfolios cascades on delete.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, IdMixin

if TYPE_CHECKING:
    from app.db.models.portfolio import Portfolio


class Position(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id",
            "ticker",
            "exchange",
            name="uq_positions_portfolio_ticker_exchange",
        ),
        CheckConstraint(
            "asset_type IN ('equity','etf','crypto','bond','other')",
            name="ck_positions_asset_type",
        ),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticker: Mapped[str] = mapped_column(String, nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(
        String, nullable=False, default="equity", server_default="equity"
    )
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    cost_basis: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    currency: Mapped[str] = mapped_column(
        String, nullable=False, default="USD", server_default="USD"
    )
    exchange: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    portfolio: Mapped["Portfolio"] = relationship(
        "Portfolio", back_populates="positions"
    )
