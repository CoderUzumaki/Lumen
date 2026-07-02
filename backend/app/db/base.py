"""SQLAlchemy declarative base + shared column mixins + async engine wiring.

Every ORM model inherits from `Base`. The shared columns (id, created_at,
updated_at) are provided by mixins so tables can opt in only to what they
actually need — `user_preferences` uses its own natural key, `positions` /
`themes` have no `updated_at`, etc.

Runtime uses `asyncpg` via `AsyncEngine` + `AsyncSession`. Alembic runs
synchronously with `psycopg2` — see `alembic/env.py` for the driver swap.

Deviation from BOOT-05: BUILD.md's BOOT-05 spec put `id` / `created_at` /
`updated_at` on Base directly. DATA-01's schema requires per-table opt-in
(user_preferences has no `id`; positions / themes have no `updated_at`).
Refactored to mixins here; every subsequent model composes what it needs.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.config import Config


class Base(DeclarativeBase):
    """Bare declarative base. Models compose mixins for shared columns."""

    pass


class IdMixin:
    """UUID primary key, defaults to `uuid.uuid4()` on insert."""

    id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class CreatedAtMixin:
    """Server-generated `created_at` timestamp."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class TimestampsMixin(CreatedAtMixin):
    """`created_at` + `updated_at`. Extends CreatedAtMixin so you can pick
    one or both without duplicate column declarations."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# --- Async engine + session factory (lazy) ----------------------------------

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(Config.DATABASE_URL, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db_session() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        yield session
