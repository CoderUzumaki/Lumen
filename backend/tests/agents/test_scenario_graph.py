"""SIM-02 acceptance: LangGraph composition of the scenario simulator.

Hermetic — sqlite via `Base.metadata.create_all`, Chroma via a tempdir, LLM
via a scripted double, `fetch_prices` via an in-test callable. Mirrors the
IMP-04 test scaffold.
"""
from __future__ import annotations

import json
import math
import tempfile
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import chromadb
import pytest
import pytest_asyncio
from chromadb.config import Settings
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.db.vectorstore as vs
from app.agents.scenario.graph import (
    SCENARIO_GRAPH,
    simulate_scenario,
)
from app.db.base import Base
from app.db.models import (  # noqa: F401 register with Base.metadata
    Portfolio,
    Position,
    Theme,
)
from app.schemas.scenario import PositionImpact, ScenarioSimulation
from app.tools.prices import PriceContext
from app.utils.embeddings import EmbeddingClient
from app.utils.llm import LLMClient, LLMResponse


# --- doubles ---------------------------------------------------------------


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class _FakeEmbed(EmbeddingClient):
    """Deterministic embeddings — enough to make `retrieve_analogs` shape-work."""

    async def embed(self, texts):  # type: ignore[override]
        return [_unit([1.0, 0.0, 0.0]) for _ in texts]


class _ScriptedLLM(LLMClient):
    """LLM double that returns responses from a queue and counts invocations."""

    def __init__(self, responses):
        super().__init__(http_client=AsyncMock())
        self._responses = list(responses)
        self.calls = 0

    async def complete(self, messages, **kwargs):  # type: ignore[override]
        self.calls += 1
        if not self._responses:
            raise AssertionError(
                f"_ScriptedLLM ran out of canned responses on call {self.calls}"
            )
        payload = self._responses.pop(0)
        if hasattr(payload, "model_dump_json"):
            content = payload.model_dump_json()
            parsed = payload
        else:
            content = json.dumps(payload)
            parsed = payload
        return LLMResponse(
            content=content,
            parsed=parsed,
            model="fake",
            tier=kwargs.get("tier", "thorough"),
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
        )


# --- fixtures --------------------------------------------------------------


@pytest_asyncio.fixture
async def env() -> AsyncIterator[tuple[AsyncSession, vs.VectorStore]]:
    """Fresh sqlite + Chroma tempdir per test."""
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    chroma_path = Path(tempfile.mkdtemp(prefix="lumen-scenario-chroma-"))
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _):  # noqa: ARG001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    chroma_client = chromadb.PersistentClient(
        path=str(chroma_path), settings=Settings(anonymized_telemetry=False)
    )
    original = vs._client
    vs._client = chroma_client
    vs.init_collections(client=chroma_client)
    analogs_store = vs.VectorStore("historical_analogs", client=chroma_client)

    async with factory() as session:
        yield session, analogs_store

    vs._client = original
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass
    import shutil

    shutil.rmtree(chroma_path, ignore_errors=True)


# --- seed helpers ----------------------------------------------------------


_SCENARIO_TEXT = "Fed cuts 50bps at the next FOMC meeting"


async def _seed_portfolio(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tickers: tuple[str, ...] = ("AAPL", "MSFT"),
    with_theme: bool = True,
) -> tuple[Portfolio, list[Position]]:
    pf = Portfolio(user_id=user_id, name=f"pf-{uuid.uuid4().hex[:6]}", is_active=True)
    session.add(pf)
    await session.flush()

    positions: list[Position] = []
    for t in tickers:
        pos = Position(
            portfolio_id=pf.id,
            ticker=t,
            asset_type="equity",
            currency="USD",
            exchange="NASDAQ",
        )
        session.add(pos)
        positions.append(pos)
    await session.flush()

    if with_theme:
        session.add(
            Theme(
                user_id=user_id,
                description="rate-sensitive growth exposure",
                weight=Decimal("0.75"),
            )
        )

    await session.commit()
    for p in positions:
        await session.refresh(p)
    return pf, positions


def _clean_simulation(tickers: list[str]) -> ScenarioSimulation:
    per = [
        PositionImpact(
            ticker=t,
            mechanism=(
                "Lower policy rates reduce discount rates on future cash "
                "flows, lifting duration-sensitive equity multiples across "
                "the growth cohort via the term premium channel."
            ),
            magnitude_low=0.02,
            magnitude_high=0.06,
            confidence=0.6,
        )
        for t in tickers
    ]
    return ScenarioSimulation(
        scenario_text=_SCENARIO_TEXT,
        per_position_impact=per,
        portfolio_summary=(
            "The portfolio has meaningful exposure to rate-sensitive growth "
            "names; a 50bp cut is likely to lift multiples modestly across "
            "the book through lower discount rates."
        ),
        citations=[],
        historical_analogs=[],
        key_assumptions=[
            "market prices in the cut before the meeting",
            "front-end yields respond in sympathy",
        ],
        falsifiability=(
            "The read flips if the 10y yield rises rather than falls in the "
            "48 hours following the announcement."
        ),
    )


def _directional_simulation(tickers: list[str]) -> ScenarioSimulation:
    # `portfolio_summary` contains "you should buy TLT" — trips GRD-01 lexically
    # on both `should` and `buy`.
    sim = _clean_simulation(tickers)
    return sim.model_copy(
        update={
            "portfolio_summary": (
                "Given the expected cut, you should buy TLT to lengthen "
                "portfolio duration and capture the term-premium repricing "
                "across the growth cohort."
            ),
        }
    )


def _fake_price_context(ticker: str, lookback_days: int = 30) -> PriceContext:  # noqa: ARG001
    return PriceContext(
        ticker=ticker.upper(),
        current=Decimal("150.00"),
        pct_change_1d=0.004,
        pct_change_5d=0.018,
        pct_change_30d=0.031,
        pct_change_ytd=0.087,
        currency="USD",
    )


def _partial_prices(missing: str):
    """Return a fetch_prices that yields None only for the named ticker."""

    def _fetch(ticker: str, lookback_days: int = 30) -> PriceContext | None:  # noqa: ARG001
        if ticker.upper() == missing.upper():
            return None
        return _fake_price_context(ticker)

    return _fetch


# --- tests -----------------------------------------------------------------


def test_graph_compiles_at_import():
    assert SCENARIO_GRAPH is not None
    assert hasattr(SCENARIO_GRAPH, "ainvoke")


@pytest.mark.asyncio
async def test_happy_path_returns_simulation(env):
    session, analogs_store = env
    user_id = uuid.uuid4()
    pf, positions = await _seed_portfolio(session, user_id=user_id)

    tickers = [p.ticker for p in positions]
    llm = _ScriptedLLM([_clean_simulation(tickers)])

    result = await simulate_scenario(
        user_id,
        pf.id,
        _SCENARIO_TEXT,
        session=session,
        analogs_store=analogs_store,
        embed=_FakeEmbed(),
        llm=llm,
        fetch_prices=_fake_price_context,
    )

    assert result is not None
    assert isinstance(result, ScenarioSimulation)
    assert result.scenario_text == _SCENARIO_TEXT
    assert len(result.per_position_impact) == len(tickers)
    assert {pi.ticker for pi in result.per_position_impact} == set(tickers)
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_returns_none_for_other_users_portfolio(env):
    session, analogs_store = env
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    pf, positions = await _seed_portfolio(session, user_id=owner_id)

    tickers = [p.ticker for p in positions]
    llm = _ScriptedLLM([_clean_simulation(tickers)])

    result = await simulate_scenario(
        other_id,
        pf.id,
        _SCENARIO_TEXT,
        session=session,
        analogs_store=analogs_store,
        embed=_FakeEmbed(),
        llm=llm,
        fetch_prices=_fake_price_context,
    )

    assert result is None
    # Graph short-circuits before reaching the LLM.
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_returns_none_when_llm_parse_fails(env):
    session, analogs_store = env
    user_id = uuid.uuid4()
    pf, _positions = await _seed_portfolio(session, user_id=user_id)

    # MagicMock LLM whose `.complete` raises — mimics an OpenRouter/network
    # blowup or a Pydantic ValidationError that has already escaped the client.
    llm = MagicMock(spec=LLMClient)
    llm.complete = AsyncMock(side_effect=RuntimeError("model deserialization failed"))

    result = await simulate_scenario(
        user_id,
        pf.id,
        _SCENARIO_TEXT,
        session=session,
        analogs_store=analogs_store,
        embed=_FakeEmbed(),
        llm=llm,
        fetch_prices=_fake_price_context,
    )

    assert result is None
    llm.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_guardrail_violation_returns_none(env):
    session, analogs_store = env
    user_id = uuid.uuid4()
    pf, positions = await _seed_portfolio(session, user_id=user_id)

    tickers = [p.ticker for p in positions]
    llm = _ScriptedLLM([_directional_simulation(tickers)])

    result = await simulate_scenario(
        user_id,
        pf.id,
        _SCENARIO_TEXT,
        session=session,
        analogs_store=analogs_store,
        embed=_FakeEmbed(),
        llm=llm,
        fetch_prices=_fake_price_context,
    )

    assert result is None
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_price_context_fetch_wraps_none(env):
    session, analogs_store = env
    user_id = uuid.uuid4()
    pf, positions = await _seed_portfolio(session, user_id=user_id)

    tickers = [p.ticker for p in positions]
    llm = _ScriptedLLM([_clean_simulation(tickers)])

    # `_partial_prices("AAPL")` returns None for AAPL but real data for MSFT
    # — the graph should still complete and hit the LLM exactly once.
    result = await simulate_scenario(
        user_id,
        pf.id,
        _SCENARIO_TEXT,
        session=session,
        analogs_store=analogs_store,
        embed=_FakeEmbed(),
        llm=llm,
        fetch_prices=_partial_prices("AAPL"),
    )

    assert result is not None
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_analog_retrieval_failure_is_best_effort(env, monkeypatch):
    session, analogs_store = env
    user_id = uuid.uuid4()
    pf, positions = await _seed_portfolio(session, user_id=user_id)

    tickers = [p.ticker for p in positions]
    llm = _ScriptedLLM([_clean_simulation(tickers)])

    # Patch the tool at the callsite the graph imported it under.
    async def _boom(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError("chroma exploded")

    monkeypatch.setattr(
        "app.agents.scenario.graph.retrieve_analogs_tool", _boom
    )

    result = await simulate_scenario(
        user_id,
        pf.id,
        _SCENARIO_TEXT,
        session=session,
        analogs_store=analogs_store,
        embed=_FakeEmbed(),
        llm=llm,
        fetch_prices=_fake_price_context,
    )

    assert result is not None
    # The retrieval failure surfaces as an empty analog list — the returned
    # simulation should carry that through untouched.
    assert result.historical_analogs == []
    assert llm.calls == 1
