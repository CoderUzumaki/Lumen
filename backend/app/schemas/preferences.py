"""Pydantic v2 schemas for user preferences (DATA-02).

Backs `GET /api/me` (via DATA-05) which returns `preferences: UserPreferencesRead`.
`UserPreferencesUpdate` is the body for `PUT /api/me/preferences`; every field
is optional so callers can PATCH-shaped partial updates.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ModelTier = Literal["fast", "thorough"]

CURRENCY_PATTERN = r"^[A-Z]{3}$"


class UserPreferencesBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    briefing_hour: int = Field(default=8, ge=0, le=23)
    briefing_timezone: str = Field(default="UTC", min_length=1, max_length=64)
    display_currency: str = Field(default="USD", pattern=CURRENCY_PATTERN)
    model_tier: ModelTier = "thorough"


class UserPreferencesUpdate(BaseModel):
    """Body for `PUT /api/me/preferences`. Every field optional."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    briefing_hour: int | None = Field(default=None, ge=0, le=23)
    briefing_timezone: str | None = Field(default=None, min_length=1, max_length=64)
    display_currency: str | None = Field(default=None, pattern=CURRENCY_PATTERN)
    model_tier: ModelTier | None = None


class UserPreferencesRead(UserPreferencesBase):
    """Response body for the user's preferences row."""

    user_id: UUID
    created_at: datetime
    updated_at: datetime
