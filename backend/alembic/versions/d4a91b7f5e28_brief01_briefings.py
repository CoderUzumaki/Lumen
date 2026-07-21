"""brief01_briefings

Revision ID: d4a91b7f5e28
Revises: c3b8f4e1d7a2
Create Date: 2026-07-20

Creates `briefings` per BUILD.md BRIEF-01. FK to `portfolios` is same-DB
(portable). FK to `auth.users(id)` is Postgres-only and added conditionally
so sqlite CI can still `alembic upgrade head`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4a91b7f5e28"
down_revision: Union[str, None] = "c3b8f4e1d7a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _jsonb() -> sa.types.TypeEngine:
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def _uuid_array() -> sa.types.TypeEngine:
    return postgresql.ARRAY(postgresql.UUID(as_uuid=True)).with_variant(
        sa.JSON(), "sqlite"
    )


def upgrade() -> None:
    op.create_table(
        "briefings",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("briefing_date", sa.Date(), nullable=False),
        sa.Column("structured_content", _jsonb(), nullable=False),
        sa.Column(
            "cited_impact_ids",
            _uuid_array(),
            nullable=False,
            server_default=(
                sa.text("'{}'::uuid[]") if _is_postgres() else sa.text("'[]'")
            ),
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("generation_duration_ms", sa.Integer(), nullable=True),
        sa.Column("langsmith_run_id", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "portfolio_id",
            "briefing_date",
            name="uq_briefings_user_portfolio_date",
        ),
    )
    # Composite index on (user_id, briefing_date DESC). sqlite ignores DESC
    # on index columns for planning purposes but accepts the syntax.
    op.create_index(
        "idx_briefings_user_date",
        "briefings",
        ["user_id", sa.text("briefing_date DESC")],
    )

    if _is_postgres():
        op.create_foreign_key(
            "fk_briefings_user_id",
            "briefings",
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
            "fk_briefings_user_id",
            "briefings",
            schema="public",
            type_="foreignkey",
        )
    op.drop_index("idx_briefings_user_date", table_name="briefings")
    op.drop_table("briefings")
