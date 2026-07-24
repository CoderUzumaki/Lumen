"""SIM-01 acceptance: /api/scenarios/simulate (SSE) + /api/scenarios/presets."""
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
from app.db.models import (  # noqa: F401 register with Base.metadata
    Portfolio,
)
from app.main import app
from app.routes.scenarios import get_scenario_runner
from app.schemas.impact import Citation
from app.schemas.scenario import PositionImpact, ScenarioSimulation
from app.utils.auth import UserContext, require_auth


ALICE = uuid.uuid4()
BOB = uuid.uuid4()


def _fake_user_factory(user_id: uuid.UUID):
    async def _fake() -> UserContext:
        return UserContext(
            user_id=user_id, email=f"{user_id}@test", role="authenticated"
        )

    return _fake


class _RunnerRecorder:
    """Test double for the scenario runner — records calls, returns a canned result."""

    def __init__(self, *, result: ScenarioSimulation | None = None) -> None:
        self.calls: list[tuple[uuid.UUID, uuid.UUID, str]] = []
        self._result = result
        self.exc: BaseException | None = None

    async def __call__(
        self, user_id: uuid.UUID, portfolio_id: uuid.UUID, scenario_text: str
    ) -> ScenarioSimulation | None:
        self.calls.append((user_id, portfolio_id, scenario_text))
        if self.exc is not None:
            raise self.exc
        return self._result


def _sample_result(scenario_text: str = "Fed cuts") -> ScenarioSimulation:
    return ScenarioSimulation(
        scenario_text=scenario_text,
        per_position_impact=[
            PositionImpact(
                ticker="AAPL",
                mechanism=(
                    "Rate cuts lower the discount rate on future cash flows, "
                    "raising duration-sensitive equity multiples."
                ),
                magnitude_low=0.01,
                magnitude_high=0.05,
                confidence=0.7,
            )
        ],
        portfolio_summary=(
            "The portfolio is duration-sensitive; a 50bps cut is a tailwind "
            "for the equity book but compresses money-market income."
        ),
        citations=[
            Citation(
                source="reuters",
                url="https://reuters.example/fed",
                title="Fed cuts 50bps",
                quote="quote",
            )
        ],
        historical_analogs=[],
        key_assumptions=["Fed follows through on 50bps guidance"],
        falsifiability="Curve re-inverts within 5 sessions of the cut.",
    )


@pytest_asyncio.fixture
async def env() -> AsyncIterator[
    tuple[AsyncClient, async_sessionmaker[AsyncSession], _RunnerRecorder]
]:
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}", future=True
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _):  # noqa: ARG001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _session_override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            yield s

    runner = _RunnerRecorder(result=_sample_result())

    app.dependency_overrides[get_db_session] = _session_override
    app.dependency_overrides[require_auth] = _fake_user_factory(ALICE)
    app.dependency_overrides[get_scenario_runner] = lambda: runner

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c, session_factory, runner

    app.dependency_overrides.clear()
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass


async def _mk_portfolio(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    active: bool = True,
) -> Portfolio:
    p = Portfolio(
        user_id=user_id,
        name=f"pf-{uuid.uuid4().hex[:6]}",
        is_active=active,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


# ---------------------------------------------------------------------------
# GET /api/scenarios/presets
# ---------------------------------------------------------------------------


async def test_presets_returns_curated_list(env):
    client, _, _ = env
    r = await client.get("/api/scenarios/presets")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 8, "expected the curated presets from SIM-03"
    first = body[0]
    for key in ("id", "title", "scenario_text", "category"):
        assert key in first
    # Every id is unique and kebab-case-ish (no whitespace).
    ids = [p["id"] for p in body]
    assert len(set(ids)) == len(ids)
    for pid in ids:
        assert " " not in pid


async def test_presets_requires_auth(env):
    """Anon → 401 (matches the app-wide require_auth contract)."""
    client, _, _ = env
    app.dependency_overrides.pop(require_auth, None)
    try:
        r = await client.get("/api/scenarios/presets")
        assert r.status_code == 401
    finally:
        app.dependency_overrides[require_auth] = _fake_user_factory(ALICE)


# ---------------------------------------------------------------------------
# POST /api/scenarios/simulate
# ---------------------------------------------------------------------------


async def test_simulate_returns_sse_stream_with_result_frame(env):
    client, factory, runner = env
    async with factory() as s:
        pf = await _mk_portfolio(s, ALICE)

    r = await client.post(
        "/api/scenarios/simulate",
        json={"scenario_text": "Fed cuts 50bps at next FOMC"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    body = r.text
    assert "event: node_started" in body
    assert "event: node_completed" in body
    assert "event: result" in body
    assert "event: complete" in body

    # Runner was called with the active portfolio + the scenario text.
    assert len(runner.calls) == 1
    uid, pid, text = runner.calls[0]
    assert uid == ALICE
    assert pid == pf.id
    assert "Fed cuts" in text


async def test_simulate_uses_explicit_portfolio_when_provided(env):
    client, factory, runner = env
    async with factory() as s:
        active = await _mk_portfolio(s, ALICE, active=True)
        # A second inactive portfolio the caller owns.
        other = Portfolio(user_id=ALICE, name="Retirement", is_active=False)
        s.add(other)
        await s.commit()
        await s.refresh(other)

    r = await client.post(
        "/api/scenarios/simulate",
        json={"scenario_text": "Oil to $120", "portfolio_id": str(other.id)},
    )
    assert r.status_code == 200
    assert runner.calls[0][1] == other.id
    assert runner.calls[0][1] != active.id


async def test_simulate_404_when_no_active_portfolio(env):
    """Alice has no portfolio at all → 404 and runner not called."""
    client, _, runner = env
    r = await client.post(
        "/api/scenarios/simulate",
        json={"scenario_text": "Fed cuts"},
    )
    assert r.status_code == 404
    assert runner.calls == []


async def test_simulate_404_when_portfolio_belongs_to_other_user(env):
    client, factory, runner = env
    async with factory() as s:
        await _mk_portfolio(s, ALICE)  # Alice has her own active
        bob_pf = await _mk_portfolio(s, BOB, active=True)

    r = await client.post(
        "/api/scenarios/simulate",
        json={"scenario_text": "Fed cuts", "portfolio_id": str(bob_pf.id)},
    )
    assert r.status_code == 404
    assert runner.calls == []


async def test_simulate_error_frame_when_runner_raises(env):
    client, factory, runner = env
    async with factory() as s:
        await _mk_portfolio(s, ALICE)
    runner.exc = RuntimeError("scenario boom")

    r = await client.post(
        "/api/scenarios/simulate",
        json={"scenario_text": "Fed cuts"},
    )
    assert r.status_code == 200
    body = r.text
    assert "event: error" in body
    assert "scenario boom" in body
    # Runner recorded the call before raising.
    assert len(runner.calls) == 1


async def test_simulate_error_frame_when_runner_returns_none(env):
    """Guardrail failure / LLM parse error surfaces as an SSE error frame."""
    client, factory, runner = env
    async with factory() as s:
        await _mk_portfolio(s, ALICE)
    runner._result = None  # noqa: SLF001 — test double

    r = await client.post(
        "/api/scenarios/simulate",
        json={"scenario_text": "Fed cuts"},
    )
    assert r.status_code == 200
    body = r.text
    assert "event: error" in body
    assert "no result" in body.lower() or "guardrail" in body.lower()


async def test_simulate_validates_body_length(env):
    """Empty scenario_text → 400 (via RequestValidationError → validation_error)."""
    client, factory, _ = env
    async with factory() as s:
        await _mk_portfolio(s, ALICE)

    r = await client.post(
        "/api/scenarios/simulate",
        json={"scenario_text": ""},
    )
    assert r.status_code == 400

    r = await client.post(
        "/api/scenarios/simulate",
        json={"scenario_text": "x" * 2001},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# SIM-03: preset data sanity
# ---------------------------------------------------------------------------


async def test_get_preset_by_id_roundtrip(env):
    """Every listed preset can be looked up by its id via SIM-03's API."""
    from app.agents.scenario.presets import get_preset, list_presets

    for p in list_presets():
        found = get_preset(p.id)
        assert found is not None
        assert found.id == p.id
    assert get_preset("does-not-exist") is None
