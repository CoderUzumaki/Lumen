"""`llm_calls` — one row per LLM invocation, for benchmarking.

Full spec lives in OPT-05. BOOT-06 landed this table so the LLM wrapper has
somewhere to write; OPT-05 later adds the companion `llm_cache` table and
the semantic-lookup logic.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampsMixin


class LlmCall(IdMixin, TimestampsMixin, Base):
    __tablename__ = "llm_calls"

    agent_name: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cache_source: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True
    )
