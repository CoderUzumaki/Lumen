"""Portfolio + nested-position CRUD (DATA-03).

Ownership rule per BUILD.md: every route pulls `user_id` from `require_auth`
and scopes every query to that owner. Cross-user access returns **404 not
found** — never 403 — so existence isn't leaked.

Positions are managed under a portfolio here (list + create). Top-level
position endpoints (PUT / DELETE by position_id) live in `positions.py`.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db_session
from app.db.models.portfolio import Portfolio
from app.db.models.position import Position
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioRead,
    PortfolioUpdate,
    PositionCreate,
    PositionRead,
)
from app.utils.auth import UserContext, require_auth

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])


async def _get_owned_portfolio(
    portfolio_id: UUID, user_id: UUID, db: AsyncSession
) -> Portfolio:
    q = select(Portfolio).where(
        Portfolio.id == portfolio_id, Portfolio.user_id == user_id
    )
    obj = (await db.execute(q)).scalar_one_or_none()
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="portfolio not found"
        )
    return obj


# -- Portfolios --------------------------------------------------------------


@router.post("", response_model=PortfolioRead, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    body: PortfolioCreate,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> Portfolio:
    portfolio = Portfolio(
        user_id=user.user_id, name=body.name, is_active=body.is_active
    )
    if body.is_active:
        await db.execute(
            update(Portfolio)
            .where(Portfolio.user_id == user.user_id, Portfolio.is_active.is_(True))
            .values(is_active=False)
        )
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


@router.get("", response_model=list[PortfolioRead])
async def list_portfolios(
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> list[Portfolio]:
    q = select(Portfolio).where(Portfolio.user_id == user.user_id).order_by(
        Portfolio.created_at
    )
    return list((await db.execute(q)).scalars().all())


@router.get("/{portfolio_id}", response_model=PortfolioRead)
async def get_portfolio(
    portfolio_id: UUID,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> Portfolio:
    return await _get_owned_portfolio(portfolio_id, user.user_id, db)


@router.put("/{portfolio_id}", response_model=PortfolioRead)
async def update_portfolio(
    portfolio_id: UUID,
    body: PortfolioUpdate,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> Portfolio:
    portfolio = await _get_owned_portfolio(portfolio_id, user.user_id, db)
    changes = body.model_dump(exclude_unset=True)
    activating = changes.get("is_active") is True and not portfolio.is_active
    if activating:
        await db.execute(
            update(Portfolio)
            .where(
                Portfolio.user_id == user.user_id,
                Portfolio.id != portfolio_id,
                Portfolio.is_active.is_(True),
            )
            .values(is_active=False)
        )
    for field, value in changes.items():
        setattr(portfolio, field, value)
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


@router.delete(
    "/{portfolio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_portfolio(
    portfolio_id: UUID,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    portfolio = await _get_owned_portfolio(portfolio_id, user.user_id, db)
    await db.delete(portfolio)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{portfolio_id}/activate", response_model=PortfolioRead)
async def activate_portfolio(
    portfolio_id: UUID,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> Portfolio:
    portfolio = await _get_owned_portfolio(portfolio_id, user.user_id, db)
    # Deactivate the current active portfolio (if any, excluding target).
    await db.execute(
        update(Portfolio)
        .where(
            Portfolio.user_id == user.user_id,
            Portfolio.id != portfolio_id,
            Portfolio.is_active.is_(True),
        )
        .values(is_active=False)
    )
    portfolio.is_active = True
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


# -- Positions under a portfolio ---------------------------------------------


@router.post(
    "/{portfolio_id}/positions",
    response_model=PositionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_position(
    portfolio_id: UUID,
    body: PositionCreate,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> Position:
    portfolio = await _get_owned_portfolio(portfolio_id, user.user_id, db)
    position = Position(
        portfolio_id=portfolio.id,
        **body.model_dump(),
    )
    db.add(position)
    await db.commit()
    await db.refresh(position)
    return position


@router.get("/{portfolio_id}/positions", response_model=list[PositionRead])
async def list_positions(
    portfolio_id: UUID,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
) -> list[Position]:
    # 404 if the portfolio isn't the user's.
    await _get_owned_portfolio(portfolio_id, user.user_id, db)
    q = (
        select(Position)
        .where(Position.portfolio_id == portfolio_id)
        .order_by(Position.created_at)
    )
    return list((await db.execute(q)).scalars().all())
