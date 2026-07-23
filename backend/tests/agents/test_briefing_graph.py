"""BRIEF-02 acceptance: briefing synthesizer LangGraph."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.agents.briefing.graph import (
    BRIEFING_GRAPH,
    _FalsifiabilityList,
    _RankPick,
    _Summary,
    synthesize_briefing_for_user,
)
from app.db.base import Base
from app.db.models import (  # noqa: F401 register with Base.metadata
    Briefing,
    ImpactAssessment,
    NewsCluster,
    Portfolio,
    Position,
)
from app.utils.llm import LLMClient, LLMResponse


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
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

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s

    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass


class _ScriptedLLM(LLMClient):
    """Returns canned pydantic instances from a queue, one per `.complete()` call."""

    def __init__(self, responses: list) -> None:
        super().__init__(http_client=AsyncMock())
        self._responses = list(responses)
        self.calls = 0

    async def complete(self, messages, **kwargs):  # type: ignore[override]
        self.calls += 1
        if not self._responses:
            raise RuntimeError(f"_ScriptedLLM exhausted at call {self.calls}")
        parsed = self._responses.pop(0)
        content = (
            parsed.model_dump_json()
            if hasattr(parsed, "model_dump_json")
            else "{}"
        )
        return LLMResponse(
            content=content,
            parsed=parsed,
            model="fake",
            tier=kwargs.get("tier", "fast"),
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
        )


# --- fixture builders ------------------------------------------------------


async def _mk_portfolio(session: AsyncSession, user_id: uuid.UUID) -> Portfolio:
    p = Portfolio(
        user_id=user_id, name=f"pf-{uuid.uuid4().hex[:6]}", is_active=True
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


async def _mk_cluster(session: AsyncSession, title: str) -> NewsCluster:
    now = datetime.now(timezone.utc)
    c = NewsCluster(
        canonical_title=title,
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=[],
        entity_topics=[],
        member_sources=["newsapi"],
    )
    session.add(c)
    await session.commit()
    return c


async def _mk_impact(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    portfolio_id: uuid.UUID,
    cluster: NewsCluster,
    confidence: str,
    mechanism: str = (
        "Higher policy rates compress duration-sensitive equity valuations."
    ),
    affected_positions: list[str] | None = None,
    created_at: datetime | None = None,
    guardrail_violations: list[dict] | None = None,
) -> ImpactAssessment:
    row = ImpactAssessment(
        cluster_id=cluster.id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        mechanism=mechanism,
        confidence=Decimal(confidence),
        falsifiability="Thesis breaks if the 10y yield curve re-inverts within 5 sessions.",
        citations=[
            {"source": "reuters", "url": "https://reuters.example/x", "title": "t", "quote": "q"}
        ],
        historical_analogs=[],
        affected_positions=affected_positions or [],
        guardrail_violations=guardrail_violations,
    )
    session.add(row)
    await session.commit()
    if created_at is not None:
        row.created_at = created_at
        await session.commit()
    await session.refresh(row)
    return row


# --- tests -----------------------------------------------------------------


def test_graph_compiles_at_import():
    assert BRIEFING_GRAPH is not None
    assert hasattr(BRIEFING_GRAPH, "ainvoke")


async def test_happy_path_persists_briefing(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    # Two positions so we can prove affected_positions → tickers.
    aapl = Position(portfolio_id=pf.id, ticker="AAPL", asset_type="equity", currency="USD")
    nvda = Position(portfolio_id=pf.id, ticker="NVDA", asset_type="equity", currency="USD")
    session.add_all([aapl, nvda])
    await session.commit()
    await session.refresh(aapl)
    await session.refresh(nvda)

    # Seed 5 impacts with distinct clusters (unique constraint on (cluster,user,pf)).
    impacts: list[ImpactAssessment] = []
    for i in range(5):
        c = await _mk_cluster(session, f"Event {i}")
        imp = await _mk_impact(
            session, user_id=user_id, portfolio_id=pf.id, cluster=c,
            confidence=f"0.{60 + i}",
            affected_positions=[str(aapl.id)] if i % 2 == 0 else [str(nvda.id)],
        )
        impacts.append(imp)

    top_picks = _RankPick(
        picks=[impacts[4].id, impacts[3].id, impacts[2].id],
        one_line_summaries={
            impacts[4].id: "rate hike compresses valuations",
            impacts[3].id: "yields spike",
            impacts[2].id: "duration risk rises",
        },
    )
    watchlist_picks = _RankPick(
        picks=[impacts[1].id, impacts[0].id],
        one_line_summaries={
            impacts[1].id: "watching CPI print",
            impacts[0].id: "watching Fed presser",
        },
    )
    fals = _FalsifiabilityList(
        items=[
            "Curve re-inverts within 5 sessions",
            "CPI comes in below 3.0",
            "Fed pauses in the next meeting",
        ]
    )
    summary = _Summary(
        text="Today's news mechanically transmits via the rate channel: higher policy rates raise the discount applied to future cash flows and compress duration-sensitive multiples."
    )
    llm = _ScriptedLLM([top_picks, watchlist_picks, fals, summary])

    row = await synthesize_briefing_for_user(
        user_id, pf.id, session=session, llm=llm, briefing_date=date.today()
    )
    assert row is not None
    assert row.user_id == user_id
    assert row.portfolio_id == pf.id
    assert row.briefing_date == date.today()

    content = row.structured_content
    assert isinstance(content, dict)
    assert len(content["top_movers"]) == 3
    assert len(content["watchlist"]) == 2
    assert len(content["what_would_change_my_thinking"]) == 3
    assert "rate channel" in content["generated_summary"]

    cited = row.cited_impact_ids
    assert len(cited) == 5
    # Order: top first, then watchlist.
    assert cited[0] == str(impacts[4].id)
    assert cited[3] == str(impacts[1].id)

    assert row.generation_duration_ms is not None
    assert row.generation_duration_ms >= 0
    assert llm.calls == 4


async def test_confidence_below_0_5_filtered_returns_none(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    for i in range(3):
        c = await _mk_cluster(session, f"low-{i}")
        await _mk_impact(
            session, user_id=user_id, portfolio_id=pf.id, cluster=c,
            confidence="0.30",
        )
    # Even with a plentiful LLM queue, gather_impacts drops all rows.
    llm = _ScriptedLLM([
        _RankPick(),
        _RankPick(),
        _FalsifiabilityList(items=[]),
        _Summary(text="empty"),
    ])
    row = await synthesize_briefing_for_user(
        user_id, pf.id, session=session, llm=llm
    )
    assert row is None
    # Ranking stages still fire (they get empty candidates and return early),
    # but the LLM should NOT be invoked for empty candidate lists.
    assert llm.calls == 0


async def test_idempotent_second_call_returns_cached(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    # Two impacts so both top-movers AND watchlist LLM stages fire.
    c1 = await _mk_cluster(session, "Event 1")
    c2 = await _mk_cluster(session, "Event 2")
    imp1 = await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id, cluster=c1, confidence="0.80"
    )
    imp2 = await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id, cluster=c2, confidence="0.70"
    )
    llm = _ScriptedLLM([
        _RankPick(picks=[imp1.id], one_line_summaries={imp1.id: "top"}),
        _RankPick(picks=[imp2.id], one_line_summaries={imp2.id: "watch"}),
        _FalsifiabilityList(items=["fals"]),
        _Summary(text="a summary"),
    ])
    first = await synthesize_briefing_for_user(
        user_id, pf.id, session=session, llm=llm, briefing_date=date.today()
    )
    second = await synthesize_briefing_for_user(
        user_id, pf.id, session=session, llm=llm, briefing_date=date.today()
    )
    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert llm.calls == 4  # only the first call spent LLM budget


async def test_force_replaces_row(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    c1 = await _mk_cluster(session, "Event 1")
    c2 = await _mk_cluster(session, "Event 2")
    imp1 = await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id, cluster=c1, confidence="0.80"
    )
    imp2 = await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id, cluster=c2, confidence="0.70"
    )
    llm = _ScriptedLLM([
        _RankPick(picks=[imp1.id], one_line_summaries={imp1.id: "first-top"}),
        _RankPick(picks=[imp2.id], one_line_summaries={imp2.id: "first-watch"}),
        _FalsifiabilityList(items=["f"]),
        _Summary(text="first summary"),
        # second run
        _RankPick(picks=[imp1.id], one_line_summaries={imp1.id: "second-top"}),
        _RankPick(picks=[imp2.id], one_line_summaries={imp2.id: "second-watch"}),
        _FalsifiabilityList(items=["f2"]),
        _Summary(text="second summary"),
    ])
    first = await synthesize_briefing_for_user(
        user_id, pf.id, session=session, llm=llm, briefing_date=date.today()
    )
    second = await synthesize_briefing_for_user(
        user_id, pf.id, session=session, llm=llm, briefing_date=date.today(), force=True
    )
    assert first is not None and second is not None
    assert second.id != first.id
    assert second.structured_content["generated_summary"] == "second summary"
    # Confirm only one row survives (unique constraint).
    rows = list(
        (
            await session.execute(
                select(Briefing).where(Briefing.user_id == user_id)
            )
        ).scalars().all()
    )
    assert len(rows) == 1


async def test_hallucinated_impact_id_filtered_out(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    c = await _mk_cluster(session, "Event")
    imp = await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id, cluster=c, confidence="0.80"
    )
    ghost = uuid.uuid4()
    llm = _ScriptedLLM([
        _RankPick(picks=[ghost, imp.id, ghost], one_line_summaries={imp.id: "ok"}),
        _RankPick(),
        _FalsifiabilityList(items=["f"]),
        _Summary(text="a summary"),
    ])
    row = await synthesize_briefing_for_user(
        user_id, pf.id, session=session, llm=llm
    )
    assert row is not None
    assert row.cited_impact_ids == [str(imp.id)]


async def test_guardrail_directional_violation_blocks_persistence(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    c = await _mk_cluster(session, "Event")
    imp = await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id, cluster=c, confidence="0.80"
    )
    llm = _ScriptedLLM([
        _RankPick(picks=[imp.id], one_line_summaries={imp.id: "you should buy TLT"}),
        _RankPick(),
        _FalsifiabilityList(items=["a falsifiability item"]),
        _Summary(text="the reader should add duration exposure"),
    ])
    row = await synthesize_briefing_for_user(
        user_id, pf.id, session=session, llm=llm
    )
    assert row is None
    # No briefing persisted despite the LLM having produced text.
    rows = list(
        (
            await session.execute(
                select(Briefing).where(Briefing.user_id == user_id)
            )
        ).scalars().all()
    )
    assert rows == []


async def test_affected_positions_resolves_to_tickers(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    nvda = Position(portfolio_id=pf.id, ticker="NVDA", asset_type="equity", currency="USD")
    session.add(nvda)
    await session.commit()
    await session.refresh(nvda)

    c = await _mk_cluster(session, "NVDA earnings")
    imp = await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id, cluster=c,
        confidence="0.80", affected_positions=[str(nvda.id)],
    )
    llm = _ScriptedLLM([
        _RankPick(picks=[imp.id], one_line_summaries={imp.id: "revenue beat"}),
        _RankPick(),
        _FalsifiabilityList(items=["a falsifiability item"]),
        _Summary(text="a valid mechanism-focused summary of today's news"),
    ])
    row = await synthesize_briefing_for_user(
        user_id, pf.id, session=session, llm=llm
    )
    assert row is not None
    top = row.structured_content["top_movers"]
    assert top[0]["affected_positions"] == ["NVDA"]


async def test_skips_impacts_with_guardrail_violations(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    good_cluster = await _mk_cluster(session, "Good")
    bad_cluster = await _mk_cluster(session, "Bad")
    good = await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id, cluster=good_cluster,
        confidence="0.60",
    )
    await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id, cluster=bad_cluster,
        confidence="0.99",
        guardrail_violations=[{"stage": "directional", "reason": "buy detected"}],
    )
    llm = _ScriptedLLM([
        _RankPick(picks=[good.id], one_line_summaries={good.id: "clean"}),
        _RankPick(),
        _FalsifiabilityList(items=["a falsifiability item"]),
        _Summary(text="a summary body mentioning the good impact only"),
    ])
    row = await synthesize_briefing_for_user(
        user_id, pf.id, session=session, llm=llm
    )
    assert row is not None
    # The bad impact must not appear.
    assert row.cited_impact_ids == [str(good.id)]


async def test_gather_impacts_respects_lookback_hours(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    fresh_cluster = await _mk_cluster(session, "Fresh")
    old_cluster = await _mk_cluster(session, "Old")
    fresh = await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id, cluster=fresh_cluster,
        confidence="0.60",
    )
    await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id, cluster=old_cluster,
        confidence="0.99",
        created_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    llm = _ScriptedLLM([
        _RankPick(picks=[fresh.id], one_line_summaries={fresh.id: "clean"}),
        _RankPick(),
        _FalsifiabilityList(items=["a falsifiability item"]),
        _Summary(text="a valid mechanism-focused summary"),
    ])
    row = await synthesize_briefing_for_user(
        user_id, pf.id, session=session, llm=llm, lookback_hours=24
    )
    assert row is not None
    assert row.cited_impact_ids == [str(fresh.id)]
