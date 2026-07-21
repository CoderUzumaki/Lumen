"""`briefings` — persisted daily briefing per (user, portfolio, date) (BRIEF-01).

One row per (user_id, portfolio_id, briefing_date) — enforced by the unique
constraint. Populated by the BRIEF-02 synthesizer agent from the day's impact
assessments; `cited_impact_ids` names the `impact_assessments.id` rows the
narrative was constructed from.

Portability rules mirror `RelevanceScore` / `ImpactAssessment`:

- FK to `auth.users(id)` is Postgres-only; the migration adds it conditionally
  so sqlite CI still applies cleanly.
- `structured_content` is `JSONB` on Postgres, `JSON` on sqlite via
  `.with_variant()`.
- `cited_impact_ids` wire-type is `list[str]` — sqlite's default JSON encoder
  can't handle `uuid.UUID`; callers `str(id)` at the boundary. Postgres's
  `ARRAY(UUID)` accepts strings transparently.

`generated_at` (the spec's timestamp) is declared on the model directly
instead of composing `CreatedAtMixin` — the spec names one timestamp and we
respect it verbatim.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import (
    ARRAY,
    JSONB,
    UUID as PostgresUUID,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin


class Briefing(IdMixin, Base):
    __tablename__ = "briefings"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "portfolio_id",
            "briefing_date",
            name="uq_briefings_user_portfolio_date",
        ),
        Index(
            "idx_briefings_user_date",
            "user_id",
            "briefing_date",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False
    )
    portfolio_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    briefing_date: Mapped[date] = mapped_column(Date, nullable=False)
    structured_content: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=False,
    )
    # Wire type is `list[str]` so the sqlite JSON variant round-trips cleanly
    # (json.dumps can't handle UUID). Callers should str(id) before assigning.
    cited_impact_ids: Mapped[list[str]] = mapped_column(
        ARRAY(PostgresUUID(as_uuid=False)).with_variant(JSON, "sqlite"),
        nullable=False,
        default=list,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    generation_duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    langsmith_run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
