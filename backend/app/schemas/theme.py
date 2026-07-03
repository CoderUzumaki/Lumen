"""Pydantic v2 schemas for user themes (DATA-02).

Validation per BUILD.md DATA-02:
- description: 3–200 chars.
- weight: 0.0–1.0.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ThemeBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str = Field(min_length=3, max_length=200)
    weight: Decimal = Field(default=Decimal("1.0"), ge=Decimal("0"), le=Decimal("1"))


class ThemeCreate(ThemeBase):
    """Body for `POST /api/themes`."""


class ThemeUpdate(BaseModel):
    """Body for `PUT /api/themes/{id}`. Every field optional."""

    model_config = ConfigDict(from_attributes=True)

    description: str | None = Field(default=None, min_length=3, max_length=200)
    weight: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))


class ThemeRead(ThemeBase):
    """Response body for a theme."""

    id: UUID
    user_id: UUID
    embedding_id: str | None = None
    created_at: datetime
