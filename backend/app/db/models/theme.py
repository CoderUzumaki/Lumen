"""`themes` — user-authored macro themes (e.g., "recession risk", "AI capex").

Per DATA-01: has `created_at` but no `updated_at`. `embedding_id` is a
free-form reference to the vector store (Chroma will use it once ING-07
lands the embedding pipeline). Weight in [0, 1] scales relevance during
scoring.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin


class Theme(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "themes"
    __table_args__ = (
        CheckConstraint(
            "weight BETWEEN 0 AND 1",
            name="ck_themes_weight",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("1.0"), server_default="1.0"
    )
    embedding_id: Mapped[str | None] = mapped_column(String, nullable=True)
