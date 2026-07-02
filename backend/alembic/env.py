from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# BOOT-05 will extend this file to import app.db.base:Base.metadata as
# target_metadata and to wire the sync driver swap consistently. For BOOT-02
# the goal is only that `alembic revision --autogenerate` runs and produces an
# empty migration (no models declared yet).

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sync_database_url() -> str:
    """Compose an Alembic-compatible sync DB URL from DATABASE_URL.

    Alembic runs synchronously, so if the runtime uses asyncpg we swap to the
    sync psycopg driver here. Falls back to a local sqlite scratch file when
    DATABASE_URL is unset, so `alembic revision --autogenerate` works during
    BOOT-02 acceptance runs without a live Postgres.
    """
    url = os.environ.get("DATABASE_URL", "sqlite:///./_alembic_scratch.db")
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    return url


config.set_main_option("sqlalchemy.url", _sync_database_url())

# No models registered yet at BOOT-02, but Alembic needs a MetaData for
# --autogenerate to run at all. Import the empty Base.metadata so the
# autogenerate acceptance produces an empty migration. BOOT-05 will extend
# app.db.base with real models; this line then Just Works.
from app.db.base import Base  # noqa: E402
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
