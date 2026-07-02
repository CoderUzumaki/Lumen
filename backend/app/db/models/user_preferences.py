"""`user_preferences` — one row per user, natural key on user_id.

Per DATA-01: `user_id` is BOTH the primary key AND the FK to `auth.users(id)`.
Every field has a sensible default (briefing_hour=8, timezone=UTC, currency=USD,
model_tier=thorough), so the row can be materialized lazily on first login.

The FK to `auth.users` lives in the migration (Postgres only) — the model
declares `user_id` as a plain UUID so the schema is portable to sqlite in CI.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampsMixin


class UserPreferences(TimestampsMixin, Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint(
            "briefing_hour BETWEEN 0 AND 23",
            name="ck_user_preferences_briefing_hour",
        ),
        CheckConstraint(
            "model_tier IN ('fast','thorough')",
            name="ck_user_preferences_model_tier",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
    )
    briefing_hour: Mapped[int] = mapped_column(
        Integer, nullable=False, default=8, server_default="8"
    )
    briefing_timezone: Mapped[str] = mapped_column(
        String, nullable=False, default="UTC", server_default="UTC"
    )
    display_currency: Mapped[str] = mapped_column(
        String, nullable=False, default="USD", server_default="USD"
    )
    model_tier: Mapped[str] = mapped_column(
        String, nullable=False, default="thorough", server_default="thorough"
    )
