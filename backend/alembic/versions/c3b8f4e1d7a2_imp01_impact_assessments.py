"""imp01_impact_assessments

Revision ID: c3b8f4e1d7a2
Revises: b8ef3a217c04
Create Date: 2026-07-17

Creates `impact_assessments` per BUILD.md IMP-01. FKs to `news_clusters` and
`portfolios` are same-DB (portable). FK to `auth.users(id)` is Postgres-only
and added conditionally so sqlite CI can still `alembic upgrade head`.

The CHECK ensuring `citations` is a non-empty JSON array is dialect-conditional:
`jsonb_array_length(citations) >= 1` on Postgres, `json_array_length(citations)
>= 1` on sqlite. Both dialects reject inserts of `[]` for citations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c3b8f4e1d7a2"
down_revision: Union[str, None] = "b8ef3a217c04"
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
    # sqlite doesn't support ALTER TABLE ADD CONSTRAINT — the CHECK for
    # citations non-emptiness must therefore be inline in CREATE TABLE, with
    # dialect-appropriate SQL (postgres jsonb vs. sqlite json).
    citations_check_sql = (
        "jsonb_array_length(citations) >= 1"
        if _is_postgres()
        else "json_array_length(citations) >= 1"
    )

    op.create_table(
        "impact_assessments",
        sa.Column("cluster_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("portfolio_id", sa.UUID(), nullable=False),
        sa.Column("mechanism", sa.Text(), nullable=False),
        sa.Column("magnitude_low", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("magnitude_high", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("timeframe_days", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("falsifiability", sa.Text(), nullable=False),
        sa.Column("citations", _jsonb(), nullable=False),
        sa.Column(
            "historical_analogs",
            _jsonb(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "affected_positions",
            _uuid_array(),
            nullable=False,
            server_default=(
                sa.text("'{}'::uuid[]") if _is_postgres() else sa.text("'[]'")
            ),
        ),
        sa.Column("raw_llm_output", sa.Text(), nullable=True),
        sa.Column(
            "guardrail_violations",
            _jsonb(),
            nullable=True,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("langsmith_run_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="ck_impact_assessments_confidence",
        ),
        sa.CheckConstraint(
            "timeframe_days IS NULL OR timeframe_days BETWEEN 1 AND 365",
            name="ck_impact_assessments_timeframe",
        ),
        sa.CheckConstraint(
            citations_check_sql,
            name="ck_impact_assessments_citations_nonempty",
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
            name="uq_impact_assessments_cluster_user_portfolio",
        ),
    )
    op.create_index(
        "idx_impact_user_created",
        "impact_assessments",
        ["user_id", sa.text("created_at DESC")],
    )

    if _is_postgres():
        op.create_foreign_key(
            "fk_impact_assessments_user_id",
            "impact_assessments",
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
            "fk_impact_assessments_user_id",
            "impact_assessments",
            schema="public",
            type_="foreignkey",
        )
    op.drop_index("idx_impact_user_created", table_name="impact_assessments")
    op.drop_table("impact_assessments")
