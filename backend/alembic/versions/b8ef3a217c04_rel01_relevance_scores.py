"""rel01_relevance_scores

Revision ID: b8ef3a217c04
Revises: a1c4e5f2d901
Create Date: 2026-07-03

Creates `relevance_scores` per BUILD.md REL-01. FKs to `news_clusters` and
`portfolios` are same-DB (portable). FK to `auth.users(id)` is Postgres-only
and added conditionally so sqlite CI can still `alembic upgrade head`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b8ef3a217c04"
down_revision: Union[str, None] = "a1c4e5f2d901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _uuid_array() -> sa.types.TypeEngine:
    return postgresql.ARRAY(postgresql.UUID(as_uuid=True)).with_variant(
        sa.JSON(), "sqlite"
    )


def upgrade() -> None:
    op.create_table(
        "relevance_scores",
        sa.Column("cluster_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("touched_position_ids", _uuid_array(), nullable=False),
        sa.Column("touched_theme_ids", _uuid_array(), nullable=False),
        sa.Column("rationale", sa.String(), nullable=True),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "score BETWEEN 0 AND 1", name="ck_relevance_scores_score"
        ),
        sa.CheckConstraint(
            "stage IN ('prefilter','classifier')",
            name="ck_relevance_scores_stage",
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"], ["news_clusters.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cluster_id",
            "user_id",
            "portfolio_id",
            name="uq_relevance_scores_cluster_user_portfolio",
        ),
    )
    # Composite index on (user_id, score DESC). sqlite ignores DESC on index
    # columns for planning purposes but accepts the syntax.
    op.create_index(
        "idx_relevance_user_score",
        "relevance_scores",
        ["user_id", sa.text("score DESC")],
    )

    if _is_postgres():
        op.create_foreign_key(
            "fk_relevance_scores_user_id",
            "relevance_scores",
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
            "fk_relevance_scores_user_id",
            "relevance_scores",
            schema="public",
            type_="foreignkey",
        )
    op.drop_index("idx_relevance_user_score", table_name="relevance_scores")
    op.drop_table("relevance_scores")
