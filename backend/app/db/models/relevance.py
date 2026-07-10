"""`relevance_scores` — per (cluster, user, portfolio) verdict (REL-01).

One row per (cluster_id, user_id, portfolio_id) — enforced by the unique
constraint. `stage` says whether the prefilter (REL-02) short-circuited or
the classifier (REL-03) produced the score. `touched_position_ids` /
`touched_theme_ids` name the entities the classifier decided this cluster
materially affects.

FK to `auth.users(id)` is Postgres-only — the migration adds it conditionally
so sqlite CI still applies cleanly. FKs to `news_clusters` and `portfolios`
are same-DB and portable.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin


class RelevanceScore(IdMixin, Base):
    __tablename__ = "relevance_scores"
    __table_args__ = (
        CheckConstraint(
            "score BETWEEN 0 AND 1", name="ck_relevance_scores_score"
        ),
        CheckConstraint(
            "stage IN ('prefilter','classifier')",
            name="ck_relevance_scores_stage",
        ),
        UniqueConstraint(
            "cluster_id",
            "user_id",
            "portfolio_id",
            name="uq_relevance_scores_cluster_user_portfolio",
        ),
        Index(
            "idx_relevance_user_score",
            "user_id",
            "score",
        ),
    )

    cluster_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("news_clusters.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False
    )
    portfolio_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    # Wire type is `list[str]` so the sqlite JSON variant round-trips cleanly
    # (json.dumps can't handle UUID). Callers should str(id) before assigning.
    # On Postgres this still lands in a TEXT[] column; SQLAlchemy coerces the
    # str values transparently.
    touched_position_ids: Mapped[list[str]] = mapped_column(
        ARRAY(PostgresUUID(as_uuid=False)).with_variant(JSON, "sqlite"),
        nullable=False,
        default=list,
    )
    touched_theme_ids: Mapped[list[str]] = mapped_column(
        ARRAY(PostgresUUID(as_uuid=False)).with_variant(JSON, "sqlite"),
        nullable=False,
        default=list,
    )
    rationale: Mapped[str | None] = mapped_column(String, nullable=True)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
