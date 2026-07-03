"""DATA-05 acceptance: /api/me auto-creates prefs; PUT updates + validates."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base, get_db_session
from app.db.models import UserPreferences  # noqa: F401  register with Base.metadata
from app.main import app
from app.utils.auth import UserContext, require_auth


ALICE = uuid.uuid4()


def _fake_user(user_id: uuid.UUID = ALICE, email: str = "alice@example.com"):
    async def _dep() -> UserContext:
        return UserContext(user_id=user_id, email=email, role="authenticated")

    return _dep


@pytest_asyncio.fixture
async def client_and_session() -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
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
    app.dependency_overrides[require_auth] = _fake_user()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass


async def test_first_get_me_returns_defaults(client_and_session):
    client, session_factory = client_and_session

    # sanity: no row exists before the first GET
    async with session_factory() as s:
        row = (
            await s.execute(select(UserPreferences).where(UserPreferences.user_id == ALICE))
        ).scalar_one_or_none()
        assert row is None

    r = await client.get("/api/me")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == str(ALICE)
    assert body["email"] == "alice@example.com"
    prefs = body["preferences"]
    assert prefs["briefing_hour"] == 8
    assert prefs["briefing_timezone"] == "UTC"
    assert prefs["display_currency"] == "USD"
    assert prefs["model_tier"] == "thorough"
    assert prefs["user_id"] == str(ALICE)

    # And a row now exists.
    async with session_factory() as s:
        row = (
            await s.execute(select(UserPreferences).where(UserPreferences.user_id == ALICE))
        ).scalar_one()
        assert row.briefing_hour == 8


async def test_get_me_is_idempotent(client_and_session):
    client, session_factory = client_and_session

    for _ in range(3):
        r = await client.get("/api/me")
        assert r.status_code == 200

    async with session_factory() as s:
        rows = (
            await s.execute(select(UserPreferences).where(UserPreferences.user_id == ALICE))
        ).scalars().all()
        assert len(rows) == 1


async def test_put_preferences_persists_and_validates(client_and_session):
    client, session_factory = client_and_session

    # Bootstrap the row first.
    await client.get("/api/me")

    # Partial update: change briefing_hour + model_tier only.
    r = await client.put(
        "/api/me/preferences",
        json={"briefing_hour": 6, "model_tier": "fast"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["briefing_hour"] == 6
    assert body["model_tier"] == "fast"
    # Untouched fields keep their defaults.
    assert body["briefing_timezone"] == "UTC"
    assert body["display_currency"] == "USD"

    # Persisted?
    r = await client.get("/api/me")
    assert r.json()["preferences"]["briefing_hour"] == 6
    assert r.json()["preferences"]["model_tier"] == "fast"


async def test_put_preferences_briefing_hour_out_of_range(client_and_session):
    client, _ = client_and_session
    await client.get("/api/me")

    r = await client.put("/api/me/preferences", json={"briefing_hour": 99})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "validation_error"


async def test_put_preferences_invalid_model_tier(client_and_session):
    client, _ = client_and_session
    await client.get("/api/me")

    r = await client.put("/api/me/preferences", json={"model_tier": "lightning"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "validation_error"
