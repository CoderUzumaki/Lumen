"""IMP-04 acceptance: LangGraph composition of the impact analyst.

Hermetic — sqlite via `Base.metadata.create_all`, Chroma via a tempdir, LLM
via a scripted double, `fetch_prices` via an in-test callable. No live
network calls.
"""
from __future__ import annotations

import json
import math
import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import chromadb
import pytest
import pytest_asyncio
from chromadb.config import Settings
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.db.vectorstore as vs
from app.agents.impact.graph import (
    IMPACT_GRAPH,
    analyze_impact_for_user,
)
from app.db.base import Base
from app.db.models import (  # noqa: F401 register with Base.metadata
    ImpactAssessment,
    NewsCluster,
    NewsItem,
    Portfolio,
    Position,
    RelevanceScore,
    Theme,
)
from app.schemas.impact import (
    Citation,
    HistoricalAnalog,
    ImpactAssessment as ImpactAssessmentPayload,
)
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

    def push(self, payload) -> None:
        self._responses.append(payload)

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
    chroma_path = Path(tempfile.mkdtemp(prefix="lumen-impact-chroma-"))
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


# --- seeding helpers -------------------------------------------------------


_SEED_URL = "https://example.com/fed-hikes-25bps"
_SEED_BODY = (
    "The Federal Reserve raised the federal funds rate target by 25 basis points, "
    "citing sticky services inflation and a resilient labour market. Chair "
    "Powell noted that duration-sensitive equity multiples typically compress "
    "when policy rates rise, though the pace of compression depends on the path "
    "of the front end."
)
_QUOTE = "duration-sensitive equity multiples typically compress"


async def _seed_all(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> tuple[NewsCluster, Portfolio, Position]:
    now = datetime.now(timezone.utc)
    cluster = NewsCluster(
        canonical_title="Fed hikes rates 25bps",
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=["AAPL"],
        entity_topics=["rates"],
        member_sources=["newsapi"],
    )
    session.add(cluster)
    await session.flush()

    item = NewsItem(
        cluster_id=cluster.id,
        source="newsapi",
        url=_SEED_URL,
        url_hash=uuid.uuid4().hex,
        title="Fed hikes rates 25bps",
        body=_SEED_BODY,
        published_at=now,
    )
    session.add(item)

    pf = Portfolio(user_id=user_id, name=f"pf-{uuid.uuid4().hex[:6]}", is_active=True)
    session.add(pf)
    await session.flush()

    pos = Position(
        portfolio_id=pf.id,
        ticker="AAPL",
        asset_type="equity",
        currency="USD",
        exchange="NASDAQ",
    )
    session.add(pos)
    await session.flush()

    # Populate the relevance row so the graph's `load_context` picks up the
    # touched position instead of falling back to the full portfolio.
    session.add(
        RelevanceScore(
            cluster_id=cluster.id,
            user_id=user_id,
            portfolio_id=pf.id,
            score=Decimal("0.75"),
            touched_position_ids=[str(pos.id)],
            touched_theme_ids=[],
            stage="classifier",
            rationale="rate hike compresses growth multiples",
        )
    )

    await session.commit()
    return cluster, pf, pos


def _clean_payload(position_id: uuid.UUID) -> ImpactAssessmentPayload:
    return ImpactAssessmentPayload(
        mechanism=(
            "Higher policy rates raise discount rates on future cash flows, "
            "compressing duration-sensitive equity multiples across the "
            "growth cohort. Transmission is via the term premium and the "
            "front-end path."
        ),
        magnitude_low=-0.05,
        magnitude_high=-0.02,
        timeframe_days=30,
        confidence=0.65,
        falsifiability="The read flips if the 10y yield curve re-inverts within 5 sessions.",
        citations=[
            Citation(
                source="newsapi",
                url=_SEED_URL,  # type: ignore[arg-type]
                title="Fed hikes rates 25bps",
                quote=_QUOTE,
            )
        ],
        historical_analogs=[
            HistoricalAnalog(
                event_description="Fed hike March 2022",
                when=date(2022, 3, 16),
                outcome_description="Growth cohort compressed ~5% over the following month.",
                similarity_score=0.72,
            )
        ],
        affected_positions=[position_id],
    )


def _bad_directional_payload(position_id: uuid.UUID) -> ImpactAssessmentPayload:
    # Trips GRD-01 lexically via "buy".
    return ImpactAssessmentPayload(
        mechanism=(
            "Given rate hikes, you should buy TLT as a hedge because "
            "duration-sensitive assets absorb the shock most directly and "
            "the transmission is well-understood by the market."
        ),
        magnitude_low=-0.05,
        magnitude_high=-0.02,
        timeframe_days=30,
        confidence=0.65,
        falsifiability="Falsifiable if 10y yields collapse within 5 sessions of the print.",
        citations=[
            Citation(
                source="newsapi",
                url=_SEED_URL,  # type: ignore[arg-type]
                title="Fed hikes rates 25bps",
                quote=_QUOTE,
            )
        ],
        historical_analogs=[],
        affected_positions=[position_id],
    )


def _hallucinated_citation_payload(position_id: uuid.UUID) -> ImpactAssessmentPayload:
    return ImpactAssessmentPayload(
        mechanism=(
            "Policy tightening raises the discount rate on future cash "
            "flows, compressing multiples for long-duration equity via the "
            "term premium channel; transmission is proportional to duration."
        ),
        magnitude_low=-0.05,
        magnitude_high=-0.02,
        timeframe_days=30,
        confidence=0.6,
        falsifiability="Read reverses if the 10y curve re-inverts within 5 sessions.",
        citations=[
            Citation(
                source="hallucinated",
                url="https://not-a-real-source.example/xxx",  # type: ignore[arg-type]
                title="Fabricated wire",
                quote="fictional headline text",
            )
        ],
        historical_analogs=[],
        affected_positions=[position_id],
    )


def _fake_price_context(ticker: str, lookback_days: int = 30) -> PriceContext:  # noqa: ARG001
    return PriceContext(
        ticker=ticker.upper(),
        current=Decimal("150.00"),
        pct_change_1d=-0.005,
        pct_change_5d=-0.021,
        pct_change_30d=-0.037,
        pct_change_ytd=-0.088,
        currency="USD",
    )


def _no_price(ticker: str, lookback_days: int = 30) -> None:  # noqa: ARG001
    return None


# --- tests -----------------------------------------------------------------


def test_graph_compiles_at_import():
    """Acceptance: graph is compilable at import time."""
    assert IMPACT_GRAPH is not None
    assert hasattr(IMPACT_GRAPH, "ainvoke")


@pytest.mark.asyncio
async def test_happy_path_persists_row(env):
    session, analogs_store = env
    user_id = uuid.uuid4()
    cluster, pf, pos = await _seed_all(session, user_id=user_id)

    llm = _ScriptedLLM([_clean_payload(pos.id)])

    row = await analyze_impact_for_user(
        cluster.id,
        user_id,
        pf.id,
        session=session,
        analogs_store=analogs_store,
        embed=_FakeEmbed(),
        llm=llm,
        fetch_prices=_fake_price_context,
    )

    assert row is not None
    assert isinstance(row, ImpactAssessment)
    assert row.mechanism.startswith("Higher policy rates")
    assert row.falsifiability.startswith("The read flips")
    assert row.affected_positions == [str(pos.id)]
    assert len(row.citations) == 1
    assert row.citations[0]["url"].startswith(_SEED_URL)
    assert row.guardrail_violations == []
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_idempotent(env):
    session, analogs_store = env
    user_id = uuid.uuid4()
    cluster, pf, pos = await _seed_all(session, user_id=user_id)

    llm = _ScriptedLLM([_clean_payload(pos.id)])

    first = await analyze_impact_for_user(
        cluster.id, user_id, pf.id,
        session=session, analogs_store=analogs_store, embed=_FakeEmbed(),
        llm=llm, fetch_prices=_fake_price_context,
    )
    second = await analyze_impact_for_user(
        cluster.id, user_id, pf.id,
        session=session, analogs_store=analogs_store, embed=_FakeEmbed(),
        llm=llm, fetch_prices=_fake_price_context,
    )

    assert first is not None and second is not None
    assert first.id == second.id
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_force_re_runs(env):
    session, analogs_store = env
    user_id = uuid.uuid4()
    cluster, pf, pos = await _seed_all(session, user_id=user_id)

    first_payload = _clean_payload(pos.id)
    second_payload = _clean_payload(pos.id).model_copy(
        update={"confidence": 0.85, "mechanism": first_payload.mechanism + " (v2)"}
    )
    llm = _ScriptedLLM([first_payload, second_payload])

    first = await analyze_impact_for_user(
        cluster.id, user_id, pf.id,
        session=session, analogs_store=analogs_store, embed=_FakeEmbed(),
        llm=llm, fetch_prices=_fake_price_context,
    )
    assert first is not None
    assert llm.calls == 1

    second = await analyze_impact_for_user(
        cluster.id, user_id, pf.id,
        session=session, analogs_store=analogs_store, embed=_FakeEmbed(),
        llm=llm, fetch_prices=_fake_price_context, force=True,
    )
    assert second is not None
    assert second.id != first.id
    assert llm.calls == 2
    assert second.confidence == Decimal("0.85")

    # Only one row for the key.
    rows = (
        await session.execute(
            select(ImpactAssessment).where(
                ImpactAssessment.cluster_id == cluster.id,
                ImpactAssessment.portfolio_id == pf.id,
            )
        )
    ).scalars().all()
    assert len(list(rows)) == 1


@pytest.mark.asyncio
async def test_guardrail_violation_then_repair_succeeds(env):
    session, analogs_store = env
    user_id = uuid.uuid4()
    cluster, pf, pos = await _seed_all(session, user_id=user_id)

    llm = _ScriptedLLM(
        [_bad_directional_payload(pos.id), _clean_payload(pos.id)]
    )

    row = await analyze_impact_for_user(
        cluster.id, user_id, pf.id,
        session=session, analogs_store=analogs_store, embed=_FakeEmbed(),
        llm=llm, fetch_prices=_fake_price_context,
    )
    assert row is not None
    assert row.mechanism.startswith("Higher policy rates")
    assert "buy" not in row.mechanism.lower()
    assert row.guardrail_violations == []
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_persistent_violation_persists_row_with_violations(env):
    session, analogs_store = env
    user_id = uuid.uuid4()
    cluster, pf, pos = await _seed_all(session, user_id=user_id)

    llm = _ScriptedLLM(
        [_bad_directional_payload(pos.id), _bad_directional_payload(pos.id)]
    )

    row = await analyze_impact_for_user(
        cluster.id, user_id, pf.id,
        session=session, analogs_store=analogs_store, embed=_FakeEmbed(),
        llm=llm, fetch_prices=_fake_price_context,
    )
    assert row is not None  # design: we persist the final draft even if guardrails failed.
    assert llm.calls == 2  # one repair attempt only.
    assert row.guardrail_violations is not None
    assert len(row.guardrail_violations) >= 2
    assert all("directional" == v["stage"] for v in row.guardrail_violations)


@pytest.mark.asyncio
async def test_citations_validator_catches_hallucinated_url(env):
    session, analogs_store = env
    user_id = uuid.uuid4()
    cluster, pf, pos = await _seed_all(session, user_id=user_id)

    llm = _ScriptedLLM(
        [_hallucinated_citation_payload(pos.id), _clean_payload(pos.id)]
    )

    row = await analyze_impact_for_user(
        cluster.id, user_id, pf.id,
        session=session, analogs_store=analogs_store, embed=_FakeEmbed(),
        llm=llm, fetch_prices=_fake_price_context,
    )
    assert row is not None
    assert row.guardrail_violations == []
    assert llm.calls == 2
    assert row.citations[0]["url"].startswith(_SEED_URL)


@pytest.mark.asyncio
async def test_no_price_yfinance_wraps_none_gracefully(env):
    session, analogs_store = env
    user_id = uuid.uuid4()
    cluster, pf, pos = await _seed_all(session, user_id=user_id)

    llm = _ScriptedLLM([_clean_payload(pos.id)])

    row = await analyze_impact_for_user(
        cluster.id, user_id, pf.id,
        session=session, analogs_store=analogs_store, embed=_FakeEmbed(),
        llm=llm, fetch_prices=_no_price,
    )
    assert row is not None
    assert llm.calls == 1
    assert row.mechanism.startswith("Higher policy rates")
