"""Pydantic wire schemas for chat sessions and messages (CHAT-01).

Naming:
- `*Create` / `*In` — request body for POST endpoints.
- `*Read`          — response body (includes DB-generated fields).

The `Citation` shape is shared with the impact-analyst output — re-exported
from `app.schemas.impact` so a single source of truth defines source / url /
title / quote validation for both stored artifacts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.impact import Citation

__all__ = [
    "Citation",
    "ChatMessageIn",
    "ChatMessageRead",
    "ChatSessionCreate",
    "ChatSessionRead",
]


class ChatMessageIn(BaseModel):
    """Request body for POST /api/chat/sessions/{id}/messages (future endpoint)."""

    content: str = Field(min_length=1, max_length=4000)


class ChatMessageRead(BaseModel):
    """Response body for a persisted chat message."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    citations: list[Citation] = Field(default_factory=list)
    tokens_used: int | None
    langsmith_run_id: str | None
    guardrail_violations: list[dict] = Field(default_factory=list)
    created_at: datetime


class ChatSessionCreate(BaseModel):
    """Body for POST /api/chat/sessions."""

    title: str | None = Field(default=None, max_length=200)
    seed_cluster_id: UUID | None = None


class ChatSessionRead(BaseModel):
    """Response body for a chat session (with embedded messages)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    portfolio_id: UUID
    title: str | None
    seed_cluster_id: UUID | None
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageRead] = Field(default_factory=list)
