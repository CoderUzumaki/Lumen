from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic runs synchronously so we swap the asyncpg driver used at runtime
# to psycopg2 for migrations. `Config.DATABASE_URL` is the source of truth;
# `env.py` only owns the driver swap and the target_metadata wiring.
from app.db.base import Base
# Import the model registry so every mapped class registers itself with
# Base.metadata before autogenerate diffs against the live DB.
import app.db.models  # noqa: F401
from app.utils.config import Config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sync_database_url() -> str:
    """Return an Alembic-compatible sync URL.

    Priority:
      1. `DATABASE_URL` env var, if set. Swap `postgresql+asyncpg://` →
         `postgresql+psycopg2://`; leave any other dialect (sqlite, etc.)
         alone.
      2. `Config.DATABASE_URL` (which itself defaults to the local Postgres
         connection string in `Config`), same swap.
    """
    url = os.environ.get("DATABASE_URL") or Config.DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    # Bare `postgresql://` defaults to psycopg2 in SQLAlchemy, so no swap needed.
    return url


config.set_main_option("sqlalchemy.url", _sync_database_url())

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
