"""`chat_sessions` + `chat_messages` — persistent conversational context (CHAT-01).

One `ChatSession` per (user, portfolio) conversation; many `ChatMessage` rows
tied to the session. A session can optionally seed itself from a news cluster
(`seed_cluster_id`) so the initial context is anchored on a specific event.

Portability rules mirror `RelevanceScore` / `ImpactAssessment`:

- FK to `auth.users(id)` on `chat_sessions.user_id` is Postgres-only; the
  migration adds it conditionally so sqlite CI still applies cleanly.
- Postgres `JSONB` columns declare `.with_variant(JSON, "sqlite")` so
  `create_all()` emits sqlite-friendly types too.
- `seed_cluster_id` FK to `news_clusters(id)` is same-DB (portable).
- FK to `portfolios(id)` is same-DB (portable), ON DELETE CASCADE.
- Message-to-session FK is portable, ON DELETE CASCADE.

`ChatSession` composes `TimestampsMixin` (created_at + updated_at). `ChatMessage`
composes only `CreatedAtMixin` — messages are append-only.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin, TimestampsMixin


class ChatSession(IdMixin, TimestampsMixin, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index(
            "idx_chat_sessions_user_updated",
            "user_id",
            text("updated_at DESC"),
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
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed_cluster_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("news_clusters.id"),
        nullable=True,
    )


class ChatMessage(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user','assistant','system')",
            name="ck_chat_messages_role",
        ),
        Index("idx_chat_messages_session", "session_id", "created_at"),
    )

    session_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
        server_default=text("'[]'"),
        default=list,
    )
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    langsmith_run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    guardrail_violations: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
        server_default=text("'[]'"),
        default=list,
    )
