"""SQLAlchemy declarative base + async engine wiring for Lumen.

Every ORM model inherits from `Base`. `Base` provides the shared columns
`id` / `created_at` / `updated_at` per BUILD.md's BOOT-05 spec, so downstream
migrations don't need to restate them per table.

At runtime the app uses `asyncpg` (via `AsyncEngine` + `AsyncSession`).
Alembic runs synchronously and uses `psycopg2` for migrations — `env.py`
swaps the driver on the way in.
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
    """Declarative base with the columns every Lumen model shares.

    - `id`         : UUID primary key, defaults to `uuid.uuid4()` on insert.
    - `created_at` : server-generated timestamp at insert time.
    - `updated_at` : server-generated timestamp, refreshed on every UPDATE.

    Models add their own columns on top; nothing here needs to be repeated.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# --- Async engine + session factory ------------------------------------------
#
# The engine is created lazily on first access so that importing `app.db.base`
# doesn't require a valid DATABASE_URL at import time (needed for Alembic
# offline mode and for tooling that just wants the Base metadata).


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(Config.DATABASE_URL, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide async session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db_session() -> AsyncSession:
    """FastAPI dependency: yield an AsyncSession scoped to a single request.

    Usage:
        async def route(db: AsyncSession = Depends(get_db_session)) -> ...:
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session
