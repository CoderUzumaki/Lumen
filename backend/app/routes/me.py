"""`/api/me` and `/api/me/preferences` (DATA-05).

`GET /api/me` returns the caller's identity + their preferences row. The row
is materialized lazily on first hit — a brand-new user sees the DATA-01
defaults without a separate signup-time write. `PUT /api/me/preferences`
patches any subset of fields (partial-update shape via `UserPreferencesUpdate`).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db_session
from app.db.models.user_preferences import UserPreferences
from app.schemas.preferences import UserPreferencesRead, UserPreferencesUpdate
from app.utils.auth import UserContext, require_auth

router = APIRouter(prefix="/api/me", tags=["me"])


async def _get_or_create_preferences(
    user_id, db: AsyncSession
) -> UserPreferences:
    row = (
        await db.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    row = UserPreferences(user_id=user_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("")
async def get_me(
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    prefs = await _get_or_create_preferences(user.user_id, db)
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "preferences": UserPreferencesRead.model_validate(prefs).model_dump(mode="json"),
    }


@router.put("/preferences", response_model=UserPreferencesRead)
async def update_preferences(
    body: UserPreferencesUpdate,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> UserPreferences:
    prefs = await _get_or_create_preferences(user.user_id, db)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(prefs, field, value)
    await db.commit()
    await db.refresh(prefs)
    return prefs
