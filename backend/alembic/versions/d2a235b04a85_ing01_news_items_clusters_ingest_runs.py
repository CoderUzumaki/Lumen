"""ing01_news_items_clusters_ingest_runs

Revision ID: d2a235b04a85
Revises: 371a33d86850
Create Date: 2026-07-03

Adds the three Phase 2 tables per ING-01:
- news_clusters (deduped event clusters; postgres GIN on entity_tickers)
- news_items    (raw items keyed by url_hash UNIQUE; FK to clusters ON DELETE
                 SET NULL)
- ingest_runs   (per-source heartbeat rows)

Portability: `entity_tickers` / `entity_topics` are Postgres `ARRAY(String)` on
Postgres and `JSON` on sqlite via `.with_variant()`. `raw_payload` is `JSONB`
on Postgres, `JSON` on sqlite. The GIN index on `entity_tickers` is Postgres-
only. Everything else works on both dialects.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d2a235b04a85"
down_revision: Union[str, None] = "371a33d86850"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _string_array() -> sa.types.TypeEngine:
    return postgresql.ARRAY(sa.String()).with_variant(sa.JSON(), "sqlite")


def _jsonb() -> sa.types.TypeEngine:
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "ingest_runs",
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_fetched", sa.Integer(), nullable=True),
        sa.Column("items_new", sa.Integer(), nullable=True),
        sa.Column("items_deduped", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ingest_runs_source_started",
        "ingest_runs",
        ["source", "started_at"],
    )

    op.create_table(
        "news_clusters",
        sa.Column("canonical_title", sa.String(), nullable=False),
        sa.Column("canonical_summary", sa.String(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entity_tickers", _string_array(), nullable=False),
        sa.Column("entity_topics", _string_array(), nullable=False),
        sa.Column(
            "authority_score",
            sa.Numeric(precision=3, scale=2),
            server_default="0.5",
            nullable=False,
        ),
        sa.Column(
            "novelty_score",
            sa.Numeric(precision=3, scale=2),
            server_default="1.0",
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_news_clusters_first_seen", "news_clusters", ["first_seen_at"]
    )
    if _is_postgres():
        # GIN accelerates "does any of the user's tickers appear in this cluster's
        # tickers?" — the hot query in the relevance engine (REL-02). sqlite has
        # no equivalent; scans stay cheap at portfolio-project scale.
        op.execute(
            "CREATE INDEX idx_news_clusters_entity_tickers "
            "ON news_clusters USING GIN (entity_tickers)"
        )

    op.create_table(
        "news_items",
        sa.Column("cluster_id", sa.UUID(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("url_hash", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("raw_payload", _jsonb(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "source IN ('newsapi','marketaux','gdelt','edgar','rss')",
            name="ck_news_items_source",
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"], ["news_clusters.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url_hash", name="uq_news_items_url_hash"),
    )
    op.create_index("idx_news_items_cluster", "news_items", ["cluster_id"])
    op.create_index("idx_news_items_published", "news_items", ["published_at"])


def downgrade() -> None:
    op.drop_index("idx_news_items_published", table_name="news_items")
    op.drop_index("idx_news_items_cluster", table_name="news_items")
    op.drop_table("news_items")
    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS idx_news_clusters_entity_tickers")
    op.drop_index("idx_news_clusters_first_seen", table_name="news_clusters")
    op.drop_table("news_clusters")
    op.drop_index("idx_ingest_runs_source_started", table_name="ingest_runs")
    op.drop_table("ingest_runs")
