"""data01_user_prefs_portfolios_positions_themes

Revision ID: 371a33d86850
Revises: 48b25b763881
Create Date: 2026-07-03 00:47:09.716920

Adds the four Phase 1 tables per DATA-01:
- user_preferences (natural PK on user_id, FK to auth.users on Postgres)
- portfolios (id PK, FK to auth.users on Postgres, partial unique index on
  is_active=TRUE)
- positions (id PK, FK to portfolios.id ON DELETE CASCADE)
- themes (id PK, FK to auth.users on Postgres)

FKs to `auth.users(id)` are Postgres-only — that schema is Supabase's, so the
migration guards them with a dialect check. Everything else works on both
sqlite (CI) and Postgres (prod).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "371a33d86850"
down_revision: Union[str, None] = "48b25b763881"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_portfolios_user_name"),
    )
    op.create_index(
        op.f("ix_portfolios_user_id"), "portfolios", ["user_id"], unique=False
    )
    op.create_index(
        "idx_portfolios_user_active",
        "portfolios",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
        postgresql_where=sa.text("is_active = TRUE"),
    )

    op.create_table(
        "themes",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column(
            "weight",
            sa.Numeric(precision=3, scale=2),
            server_default="1.0",
            nullable=False,
        ),
        sa.Column("embedding_id", sa.String(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("weight BETWEEN 0 AND 1", name="ck_themes_weight"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_themes_user_id"), "themes", ["user_id"], unique=False)

    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("briefing_hour", sa.Integer(), server_default="8", nullable=False),
        sa.Column(
            "briefing_timezone", sa.String(), server_default="UTC", nullable=False
        ),
        sa.Column(
            "display_currency", sa.String(), server_default="USD", nullable=False
        ),
        sa.Column(
            "model_tier", sa.String(), server_default="thorough", nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "model_tier IN ('fast','thorough')",
            name="ck_user_preferences_model_tier",
        ),
        sa.CheckConstraint(
            "briefing_hour BETWEEN 0 AND 23",
            name="ck_user_preferences_briefing_hour",
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "positions",
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column(
            "asset_type", sa.String(), server_default="equity", nullable=False
        ),
        sa.Column("quantity", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("cost_basis", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("currency", sa.String(), server_default="USD", nullable=False),
        sa.Column("exchange", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "asset_type IN ('equity','etf','crypto','bond','other')",
            name="ck_positions_asset_type",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_id",
            "ticker",
            "exchange",
            name="uq_positions_portfolio_ticker_exchange",
        ),
    )
    op.create_index(
        op.f("ix_positions_portfolio_id"),
        "positions",
        ["portfolio_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_positions_ticker"), "positions", ["ticker"], unique=False
    )

    # Supabase-schema FKs are Postgres-only. Sqlite CI doesn't have auth.users.
    if _is_postgres():
        op.create_foreign_key(
            "fk_user_preferences_user_id",
            "user_preferences",
            "users",
            ["user_id"],
            ["id"],
            source_schema="public",
            referent_schema="auth",
            ondelete="CASCADE",
        )
        op.create_foreign_key(
            "fk_portfolios_user_id",
            "portfolios",
            "users",
            ["user_id"],
            ["id"],
            source_schema="public",
            referent_schema="auth",
            ondelete="CASCADE",
        )
        op.create_foreign_key(
            "fk_themes_user_id",
            "themes",
            "users",
            ["user_id"],
            ["id"],
            source_schema="public",
            referent_schema="auth",
            ondelete="CASCADE",
        )


def downgrade() -> None:
    if _is_postgres():
        op.drop_constraint(
            "fk_themes_user_id", "themes", schema="public", type_="foreignkey"
        )
        op.drop_constraint(
            "fk_portfolios_user_id",
            "portfolios",
            schema="public",
            type_="foreignkey",
        )
        op.drop_constraint(
            "fk_user_preferences_user_id",
            "user_preferences",
            schema="public",
            type_="foreignkey",
        )

    op.drop_index(op.f("ix_positions_ticker"), table_name="positions")
    op.drop_index(op.f("ix_positions_portfolio_id"), table_name="positions")
    op.drop_table("positions")
    op.drop_table("user_preferences")
    op.drop_index(op.f("ix_themes_user_id"), table_name="themes")
    op.drop_table("themes")
    op.drop_index("idx_portfolios_user_active", table_name="portfolios")
    op.drop_index(op.f("ix_portfolios_user_id"), table_name="portfolios")
    op.drop_table("portfolios")
