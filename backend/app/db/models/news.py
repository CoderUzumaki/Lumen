"""News ingestion tables (ING-01).

Three tables:
- `news_clusters` — deduped event clusters (canonical title + tickers + topics).
- `news_items`    — raw items from the five ingest sources; each optionally
                    joined to a cluster via `cluster_id`.
- `ingest_runs`   — one row per pipeline execution, for heartbeats.

Postgres-native types (`ARRAY`, `JSONB`, GIN index) are used where the DB
supports them and downgraded to `JSON` on sqlite so the CI runner can still
`alembic upgrade head`. The GIN index is added conditionally in the migration.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID

from app.db.base import Base, CreatedAtMixin, IdMixin


class NewsCluster(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "news_clusters"
    __table_args__ = (
        Index(
            "idx_news_clusters_first_seen",
            "first_seen_at",
        ),
    )

    canonical_title: Mapped[str] = mapped_column(String, nullable=False)
    canonical_summary: Mapped[str | None] = mapped_column(String, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    entity_tickers: Mapped[list[str]] = mapped_column(
        ARRAY(String).with_variant(JSON, "sqlite"),
        nullable=False,
        default=list,
    )
    entity_topics: Mapped[list[str]] = mapped_column(
        ARRAY(String).with_variant(JSON, "sqlite"),
        nullable=False,
        default=list,
    )
    authority_score: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0.5"), server_default="0.5"
    )
    novelty_score: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("1.0"), server_default="1.0"
    )


class NewsItem(IdMixin, Base):
    __tablename__ = "news_items"
    __table_args__ = (
        CheckConstraint(
            "source IN ('newsapi','marketaux','gdelt','edgar','rss')",
            name="ck_news_items_source",
        ),
        UniqueConstraint("url_hash", name="uq_news_items_url_hash"),
        Index("idx_news_items_cluster", "cluster_id"),
        Index("idx_news_items_published", "published_at"),
    )

    cluster_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("news_clusters.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    url_hash: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    raw_payload: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )


class IngestRun(IdMixin, Base):
    __tablename__ = "ingest_runs"
    __table_args__ = (
        Index("idx_ingest_runs_source_started", "source", "started_at"),
    )

    source: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    items_fetched: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_new: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_deduped: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
