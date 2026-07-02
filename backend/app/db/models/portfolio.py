"""`portfolios` — one user can have many portfolios; exactly one is active.

Per DATA-01: unique on (user_id, name); a partial unique index enforces that
at most one portfolio per user has `is_active = TRUE`. The FK to auth.users
is added in the migration for the postgresql dialect only (see comment in
`user_preferences.py`).
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampsMixin


class Portfolio(IdMixin, TimestampsMixin, Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_portfolios_user_name"),
        # Partial unique index: at most one active portfolio per user. Kept in
        # the model (not only the migration) so `Base.metadata.create_all()`
        # emits it too — the test fixture uses create_all rather than running
        # the full migration chain.
        Index(
            "idx_portfolios_user_active",
            "user_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active = TRUE"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
