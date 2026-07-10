"""REL-03 acceptance: classifier LLM plumbing + guardrail + live 10-label harness."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.agents.relevance.classifier import (
    RelevanceVerdict,
    _build_user_prompt,
    run_classifier,
)
from app.db.base import Base
from app.db.models import (  # noqa: F401 register with Base.metadata
    NewsCluster,
    NewsItem,
    Portfolio,
    Position,
    RelevanceScore,
    Theme,
)
from app.utils.llm import LLMClient, LLMResponse


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

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


async def _seed(session: AsyncSession) -> tuple[NewsCluster, Portfolio, Position, Theme, uuid.UUID]:
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    cluster = NewsCluster(
        canonical_title="Fed hikes 25bps",
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=["SPY"],
        entity_topics=[],
        member_sources=["newsapi"],
    )
    session.add(cluster)
    await session.flush()

    session.add(
        NewsItem(
            cluster_id=cluster.id,
            source="newsapi",
            url="https://reuters.example/fed",
            url_hash=uuid.uuid4().hex,
            title="Fed hikes 25bps",
            body="The FOMC raised rates by a quarter point, citing sticky inflation.",
            published_at=now,
        )
    )

    pf = Portfolio(user_id=user_id, name="Main", is_active=True)
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
    theme = Theme(
        user_id=user_id, description="US monetary policy", weight=Decimal("0.90")
    )
    session.add(theme)
    await session.commit()
    return cluster, pf, pos, theme, user_id


def _fake_llm(verdict: RelevanceVerdict) -> LLMClient:
    """LLMClient that returns a canned verdict without hitting the network."""
    client = LLMClient(http_client=AsyncMock())  # http_client won't be touched
    async def _complete(messages, **kwargs):
        return LLMResponse(
            content=verdict.model_dump_json(),
            parsed=verdict,
            model="fake",
            tier=kwargs.get("tier", "fast"),
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
        )
    client.complete = _complete  # type: ignore[assignment]
    return client


async def test_persists_classifier_row_with_touched_ids(session: AsyncSession):
    cluster, pf, pos, theme, user_id = await _seed(session)

    verdict = RelevanceVerdict(
        score=0.82,
        touched_positions=[pos.id],
        touched_themes=[theme.id],
        rationale="Higher policy rates compress duration-sensitive equity valuations.",
    )
    llm = _fake_llm(verdict)

    row = await run_classifier(
        cluster_id=cluster.id,
        portfolio_id=pf.id,
        candidate_position_ids=[pos.id],
        candidate_theme_ids=[theme.id],
        session=session,
        llm=llm,
    )

    assert row.stage == "classifier"
    assert row.score == Decimal("0.82")
    assert row.touched_position_ids == [str(pos.id)]
    assert row.touched_theme_ids == [str(theme.id)]
    assert "duration" in (row.rationale or "").lower()
    assert row.user_id == user_id


async def test_hallucinated_ids_are_filtered_out(session: AsyncSession):
    """LLM outputs a UUID not in the shortlist → the row must drop it."""
    cluster, pf, pos, _theme, _ = await _seed(session)
    ghost = uuid.uuid4()

    verdict = RelevanceVerdict(
        score=0.5,
        touched_positions=[pos.id, ghost],  # ghost isn't in the input shortlist
        touched_themes=[uuid.uuid4()],  # not in input
        rationale="mechanism.",
    )
    llm = _fake_llm(verdict)

    row = await run_classifier(
        cluster_id=cluster.id,
        portfolio_id=pf.id,
        candidate_position_ids=[pos.id],
        candidate_theme_ids=[],
        session=session,
        llm=llm,
    )
    assert row.touched_position_ids == [str(pos.id)]
    assert row.touched_theme_ids == []


async def test_score_clamped_and_rationale_persists(session: AsyncSession):
    cluster, pf, pos, _theme, _ = await _seed(session)
    verdict = RelevanceVerdict(
        score=1.0,
        touched_positions=[],
        touched_themes=[],
        rationale="  edge case rationale  ",
    )
    llm = _fake_llm(verdict)
    row = await run_classifier(
        cluster_id=cluster.id,
        portfolio_id=pf.id,
        candidate_position_ids=[],
        candidate_theme_ids=[],
        session=session,
        llm=llm,
    )
    assert row.score == Decimal("1.00")
    assert row.rationale is not None
    assert "edge case" in row.rationale


async def test_prompt_contains_title_body_positions_themes(session: AsyncSession):
    cluster, pf, pos, theme, _ = await _seed(session)
    latest_item = (
        await session.execute(
            select(NewsItem).where(NewsItem.cluster_id == cluster.id).limit(1)
        )
    ).scalar_one()
    prompt = _build_user_prompt(cluster, latest_item.body, [pos], [theme])
    assert "Fed hikes 25bps" in prompt
    assert "quarter point" in prompt
    assert "AAPL" in prompt
    assert "US monetary policy" in prompt
    assert str(pos.id) in prompt
    assert str(theme.id) in prompt


# --- Live probe (skipped by default) ----------------------------------------

_HAND_LABELED_10 = [
    # (event_title, body, ticker, expected_touched)
    ("Fed raises rates 25bps", "FOMC tightens on inflation.", "AAPL", True),
    ("Fed cuts rates 50bps", "Emergency easing move.", "TLT", True),
    ("OPEC announces production cut", "Brent surges 5%.", "XOM", True),
    ("US CPI comes in hot at 4.1%", "Bond yields spike.", "TLT", True),
    ("NVDA reports blowout earnings", "Data center revenue up 200%.", "NVDA", True),
    ("MSFT wins DoJ appeal", "Antitrust risk removed.", "MSFT", True),
    ("Small pharma announces FDA denial", "Niche biotech, no partnerships.", "AAPL", False),
    ("Local weather report from Ohio", "Sunny with clouds.", "SPY", False),
    ("Celebrity chef opens new restaurant", "Downtown venue debut.", "GOOGL", False),
    ("Country X wins soccer tournament", "Extra time drama.", "TSLA", False),
]


@pytest.mark.free_tier_live
async def test_classifier_hand_labeled_10_cases(session: AsyncSession):
    """Opt-in: run the fast-tier LLM against 10 hand-labeled cases.

    Enable with `pytest -m free_tier_live` after setting OPENROUTER_API_KEY.
    Passes when ≥ 8/10 verdicts agree with the expected 'touched' flag.
    """
    import os

    if not os.environ.get("OPENROUTER_API_KEY") or os.environ["OPENROUTER_API_KEY"] == "test-openrouter-key":
        pytest.skip("no live OPENROUTER_API_KEY configured")

    user_id = uuid.uuid4()
    pf = Portfolio(user_id=user_id, name="Live", is_active=True)
    session.add(pf)
    await session.flush()
    tickers = sorted({t for _, _, t, _ in _HAND_LABELED_10})
    position_by_ticker: dict[str, Position] = {}
    for t in tickers:
        p = Position(
            portfolio_id=pf.id, ticker=t, asset_type="equity", currency="USD", exchange="NASDAQ"
        )
        session.add(p)
        await session.flush()
        position_by_ticker[t] = p
    await session.commit()

    llm = LLMClient()
    correct = 0
    total = 0
    try:
        for title, body, ticker, expected in _HAND_LABELED_10:
            now = datetime.now(timezone.utc)
            cluster = NewsCluster(
                canonical_title=title,
                first_seen_at=now,
                last_seen_at=now,
                entity_tickers=[ticker],
                entity_topics=[],
                member_sources=["newsapi"],
            )
            session.add(cluster)
            await session.flush()
            session.add(
                NewsItem(
                    cluster_id=cluster.id,
                    source="newsapi",
                    url=f"https://example.com/{uuid.uuid4().hex}",
                    url_hash=uuid.uuid4().hex,
                    title=title,
                    body=body,
                    published_at=now,
                )
            )
            await session.commit()

            row = await run_classifier(
                cluster_id=cluster.id,
                portfolio_id=pf.id,
                candidate_position_ids=[position_by_ticker[ticker].id],
                candidate_theme_ids=[],
                session=session,
                llm=llm,
            )
            got = str(position_by_ticker[ticker].id) in row.touched_position_ids
            if got == expected:
                correct += 1
            total += 1
    finally:
        await llm.aclose()

    assert correct >= 8, f"live classifier only got {correct}/{total}"
