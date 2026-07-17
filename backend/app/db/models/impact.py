"""`impact_assessments` — structured impact-analyst output (IMP-01).

One row per (cluster_id, user_id, portfolio_id) — enforced by the unique
constraint. Populated by the IMP-04 LangGraph agent when the fan-out (REL-05)
surfaces a cluster with `stage='classifier'` above the impact threshold.

Portability rules mirror `RelevanceScore`:

- FK to `auth.users(id)` is Postgres-only; the migration adds it conditionally
  so sqlite CI still applies cleanly.
- Postgres-specific `JSONB` / `ARRAY(UUID)` columns declare `.with_variant(JSON,
  "sqlite")` so `create_all()` emits sqlite-friendly types too.
- `affected_positions` wire-type is `list[str]` — sqlite's default JSON encoder
  can't handle `uuid.UUID`; callers `str(id)` at the boundary. Postgres's
  `ARRAY(UUID)` accepts strings transparently.

The BUILD.md CHECK on `citations` non-emptiness lives in the migration
(dialect-conditional — `jsonb_array_length` on Postgres, `json_array_length`
on sqlite) rather than the model, because `create_all()` doesn't need it
(Pydantic `min_length=1` guards insert paths in the app; the DB check is a
belt-and-braces gate in production).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import (
    ARRAY,
    JSONB,
    UUID as PostgresUUID,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin


class ImpactAssessment(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "impact_assessments"
    __table_args__ = (
        CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="ck_impact_assessments_confidence",
        ),
        CheckConstraint(
            "timeframe_days IS NULL OR timeframe_days BETWEEN 1 AND 365",
            name="ck_impact_assessments_timeframe",
        ),
        UniqueConstraint(
            "cluster_id",
            "user_id",
            "portfolio_id",
            name="uq_impact_assessments_cluster_user_portfolio",
        ),
        Index("idx_impact_user_created", "user_id", "created_at"),
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
    mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    magnitude_low: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    magnitude_high: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    timeframe_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    falsifiability: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=False,
    )
    historical_analogs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=False,
        default=list,
    )
    affected_positions: Mapped[list[str]] = mapped_column(
        ARRAY(PostgresUUID(as_uuid=False)).with_variant(JSON, "sqlite"),
        nullable=False,
        default=list,
    )
    raw_llm_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    guardrail_violations: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
        default=list,
    )
    langsmith_run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
