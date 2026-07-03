"""DATA-03 acceptance: portfolios + positions CRUD, ownership, activate, validation."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base, get_db_session
from app.db.models import Portfolio, Position  # noqa: F401  register with Base.metadata
from app.main import app
from app.utils.auth import UserContext, require_auth


ALICE = uuid.uuid4()
BOB = uuid.uuid4()


def _fake_user_factory(user_id: uuid.UUID):
    async def _fake() -> UserContext:
        return UserContext(user_id=user_id, email=f"{user_id}@test", role="authenticated")

    return _fake


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Fresh sqlite per test, FastAPI dependency-override for auth + DB."""
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _):  # noqa: ARG001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _session_override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db_session] = _session_override
    app.dependency_overrides[require_auth] = _fake_user_factory(ALICE)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass


async def _as_user(client: AsyncClient, user_id: uuid.UUID):
    """Swap the authed user for this client."""
    app.dependency_overrides[require_auth] = _fake_user_factory(user_id)


# ---------------------------------------------------------------------------


async def test_owner_crud_and_activate(client: AsyncClient):
    # create
    r = await client.post("/api/portfolios", json={"name": "Main"})
    assert r.status_code == 201
    body = r.json()["data"] if "data" in r.json() else r.json()
    # Routes don't wrap in envelope (only errors do); success is bare JSON.
    body = r.json()
    portfolio_id = body["id"]
    assert body["name"] == "Main"
    assert body["is_active"] is False
    assert body["positions"] == []

    # list
    r = await client.get("/api/portfolios")
    assert r.status_code == 200
    assert len(r.json()) == 1

    # get by id
    r = await client.get(f"/api/portfolios/{portfolio_id}")
    assert r.status_code == 200
    assert r.json()["id"] == portfolio_id

    # update
    r = await client.put(f"/api/portfolios/{portfolio_id}", json={"name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"

    # create a second portfolio (inactive) then activate it — the first (already
    # inactive) doesn't need deactivation; add a third to prove the switch.
    r = await client.post("/api/portfolios", json={"name": "Retirement", "is_active": True})
    assert r.status_code == 201
    retirement_id = r.json()["id"]

    # activating the first should deactivate the second.
    r = await client.post(f"/api/portfolios/{portfolio_id}/activate")
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    r = await client.get(f"/api/portfolios/{retirement_id}")
    assert r.json()["is_active"] is False

    # add a position
    r = await client.post(
        f"/api/portfolios/{portfolio_id}/positions",
        json={"ticker": "NVDA", "quantity": "10.5", "currency": "USD"},
    )
    assert r.status_code == 201
    position_id = r.json()["id"]
    assert r.json()["ticker"] == "NVDA"

    # list positions
    r = await client.get(f"/api/portfolios/{portfolio_id}/positions")
    assert r.status_code == 200
    assert len(r.json()) == 1

    # update position
    r = await client.put(
        f"/api/positions/{position_id}", json={"quantity": "20.0"}
    )
    assert r.status_code == 200
    assert r.json()["quantity"] == "20.00000000"

    # delete position
    r = await client.delete(f"/api/positions/{position_id}")
    assert r.status_code == 204

    r = await client.get(f"/api/portfolios/{portfolio_id}/positions")
    assert r.json() == []

    # delete portfolio
    r = await client.delete(f"/api/portfolios/{portfolio_id}")
    assert r.status_code == 204
    r = await client.get(f"/api/portfolios/{portfolio_id}")
    assert r.status_code == 404


async def test_cross_user_access_returns_404(client: AsyncClient):
    # Alice creates a portfolio.
    r = await client.post("/api/portfolios", json={"name": "Alice's"})
    portfolio_id = r.json()["id"]

    # Bob adds a position to it — should 404 (portfolio not visible).
    await _as_user(client, BOB)
    r = await client.get(f"/api/portfolios/{portfolio_id}")
    assert r.status_code == 404
    r = await client.get("/api/portfolios")
    assert r.json() == []  # Bob sees his own list, which is empty
    r = await client.put(f"/api/portfolios/{portfolio_id}", json={"name": "Bob's now"})
    assert r.status_code == 404
    r = await client.delete(f"/api/portfolios/{portfolio_id}")
    assert r.status_code == 404
    r = await client.post(f"/api/portfolios/{portfolio_id}/activate")
    assert r.status_code == 404
    r = await client.post(
        f"/api/portfolios/{portfolio_id}/positions",
        json={"ticker": "NVDA"},
    )
    assert r.status_code == 404


async def test_cross_user_position_returns_404(client: AsyncClient):
    r = await client.post("/api/portfolios", json={"name": "Alice's"})
    portfolio_id = r.json()["id"]
    r = await client.post(
        f"/api/portfolios/{portfolio_id}/positions", json={"ticker": "AAPL"}
    )
    position_id = r.json()["id"]

    await _as_user(client, BOB)
    r = await client.put(f"/api/positions/{position_id}", json={"quantity": "5"})
    assert r.status_code == 404
    r = await client.delete(f"/api/positions/{position_id}")
    assert r.status_code == 404


async def test_ticker_validation_error_returns_400_with_envelope(client: AsyncClient):
    r = await client.post("/api/portfolios", json={"name": "Main"})
    portfolio_id = r.json()["id"]

    r = await client.post(
        f"/api/portfolios/{portfolio_id}/positions",
        json={"ticker": "not lowercase"},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["data"] is None
    assert body["error"]["code"] == "validation_error"
    assert "details" in body["error"]
