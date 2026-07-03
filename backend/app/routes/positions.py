"""Top-level position mutations (DATA-03).

`PUT /api/positions/{position_id}` and `DELETE /api/positions/{position_id}`
live here so callers can edit a position without needing to remember its
parent portfolio's id. Ownership is still enforced: we resolve the position
by id, then verify its portfolio belongs to the caller. Cross-user access
returns 404, matching the rule in `portfolios.py`.

Position-list-under-portfolio and position-create-under-portfolio remain in
`portfolios.py` — they're portfolio-scoped and share the ownership helper.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db_session
from app.db.models.portfolio import Portfolio
from app.db.models.position import Position
from app.schemas.portfolio import PositionRead, PositionUpdate
from app.utils.auth import UserContext, require_auth

router = APIRouter(prefix="/api/positions", tags=["positions"])


async def _get_owned_position(
    position_id: UUID, user_id: UUID, db: AsyncSession
) -> Position:
    q = (
        select(Position)
        .join(Portfolio, Portfolio.id == Position.portfolio_id)
        .where(Position.id == position_id, Portfolio.user_id == user_id)
    )
    obj = (await db.execute(q)).scalar_one_or_none()
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="position not found"
        )
    return obj


@router.put("/{position_id}", response_model=PositionRead)
async def update_position(
    position_id: UUID,
    body: PositionUpdate,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> Position:
    position = await _get_owned_position(position_id, user.user_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(position, field, value)
    await db.commit()
    await db.refresh(position)
    return position


@router.delete(
    "/{position_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_position(
    position_id: UUID,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    position = await _get_owned_position(position_id, user.user_id, db)
    await db.delete(position)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
