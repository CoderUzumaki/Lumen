"""CHAT-02 acceptance: recent-impacts / news-RAG / portfolio-summary tools."""
from __future__ import annotations

import math
import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import chromadb
import pytest_asyncio
from chromadb.config import Settings
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.db.vectorstore as vs
from app.agents.chat.retrievers import (
    ChatNewsSnippet,  # noqa: F401 — used implicitly in return type assertions
    get_portfolio_summary,
    retrieve_news,
    retrieve_recent_impacts,
)
from app.db.base import Base
from app.db.models import (  # noqa: F401 register with Base.metadata
    Briefing,
    ImpactAssessment,
    NewsCluster,
    NewsItem,
    Portfolio,
    Position,
    Theme,
)
from app.utils.embeddings import EmbeddingClient


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class _FakeEmbed(EmbeddingClient):
    """Deterministic 3D embedding: 'fed'/'aapl' → axis 0, 'pharma' → axis 1."""

    async def embed(self, texts):
        rows = []
        for t in texts:
            lo = t.lower()
            if "pharma" in lo:
                rows.append(_unit([0.0, 1.0, 0.0]))
            elif "fed" in lo or "aapl" in lo or "rate" in lo:
                rows.append(_unit([1.0, 0.0, 0.05]))
            else:
                rows.append(_unit([0.0, 0.0, 1.0]))
        return rows


@pytest_asyncio.fixture
async def env() -> AsyncIterator[
    tuple[AsyncSession, vs.VectorStore, EmbeddingClient]
]:
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    chroma_path = Path(tempfile.mkdtemp(prefix="lumen-test-chroma-"))
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

    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    chroma_client = chromadb.PersistentClient(
        path=str(chroma_path), settings=Settings(anonymized_telemetry=False)
    )
    original = vs._client
    vs._client = chroma_client
    vs.init_collections(client=chroma_client)
    news_store = vs.VectorStore("news_items", client=chroma_client)

    async with factory() as session:
        yield session, news_store, _FakeEmbed()

    vs._client = original
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass
    import shutil
    shutil.rmtree(chroma_path, ignore_errors=True)


# --- fixture builders ------------------------------------------------------


async def _mk_portfolio(
    session: AsyncSession, user_id: uuid.UUID, *, is_active: bool = True
) -> Portfolio:
    p = Portfolio(
        user_id=user_id, name=f"pf-{uuid.uuid4().hex[:6]}", is_active=is_active
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


async def _mk_position(
    session: AsyncSession, portfolio_id: uuid.UUID, ticker: str
) -> Position:
    p = Position(
        portfolio_id=portfolio_id,
        ticker=ticker,
        asset_type="equity",
        currency="USD",
        exchange="NASDAQ",
    )
    session.add(p)
    await session.commit()
    return p


async def _mk_impact(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    portfolio_id: uuid.UUID,
    cluster_id: uuid.UUID,
    confidence: str,
    created_at: datetime | None = None,
    guardrail_violations: list[dict] | None = None,
) -> ImpactAssessment:
    row = ImpactAssessment(
        cluster_id=cluster_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        mechanism="Higher rates compress duration-sensitive equity valuations.",
        confidence=Decimal(confidence),
        falsifiability="Thesis breaks if the 10y yield curve re-inverts within 5 sessions.",
        citations=[
            {
                "source": "reuters",
                "url": "https://reuters.example/x",
                "title": "t",
                "quote": "q",
            }
        ],
        historical_analogs=[],
        affected_positions=[],
        guardrail_violations=guardrail_violations,
    )
    session.add(row)
    await session.commit()
    if created_at is not None:
        # Server defaults `created_at` at insert; override for time-window tests.
        row.created_at = created_at
        await session.commit()
    await session.refresh(row)
    return row


async def _mk_cluster(
    session: AsyncSession, *, title: str, entity_tickers: list[str]
) -> NewsCluster:
    now = datetime.now(timezone.utc)
    c = NewsCluster(
        canonical_title=title,
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=entity_tickers,
        entity_topics=[],
        member_sources=["newsapi"],
    )
    session.add(c)
    await session.commit()
    return c


async def _mk_news_item(
    session: AsyncSession,
    *,
    cluster: NewsCluster,
    title: str,
    body: str,
    news_store: vs.VectorStore,
    vec: list[float],
    published_at: datetime | None = None,
) -> NewsItem:
    now = published_at or datetime.now(timezone.utc)
    item = NewsItem(
        cluster_id=cluster.id,
        source="newsapi",
        url=f"https://example.com/{uuid.uuid4().hex[:8]}",
        url_hash=uuid.uuid4().hex,
        title=title,
        body=body,
        published_at=now,
    )
    session.add(item)
    await session.commit()
    news_store.upsert(
        ids=[str(item.id)],
        embeddings=[vec],
        metadatas=[
            {
                "cluster_id": str(cluster.id),
                "source": "newsapi",
                "published_at_iso": now.isoformat(),
            }
        ],
        documents=[title],
    )
    return item


# ---------------------------------------------------------------------------
# retrieve_recent_impacts
# ---------------------------------------------------------------------------


async def test_retrieve_recent_impacts_orders_by_confidence_desc(env):
    session, _, _ = env
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    cluster = await _mk_cluster(session, title="Fed", entity_tickers=["AAPL"])
    now = datetime.now(timezone.utc)
    await _mk_impact(
        session,
        user_id=user_id,
        portfolio_id=pf.id,
        cluster_id=cluster.id,
        confidence="0.50",
        created_at=now - timedelta(hours=1),
    )
    # Cluster is unique on (cluster, user, portfolio) for impacts too — but
    # the model allows one row per triple. Need different clusters for repeats.
    c2 = await _mk_cluster(session, title="Fed2", entity_tickers=["AAPL"])
    c3 = await _mk_cluster(session, title="Fed3", entity_tickers=["AAPL"])
    await _mk_impact(
        session,
        user_id=user_id,
        portfolio_id=pf.id,
        cluster_id=c2.id,
        confidence="0.80",
        created_at=now - timedelta(hours=2),
    )
    await _mk_impact(
        session,
        user_id=user_id,
        portfolio_id=pf.id,
        cluster_id=c3.id,
        confidence="0.70",
        created_at=now - timedelta(hours=3),
    )

    got = await retrieve_recent_impacts(user_id, pf.id, session=session, k=3)
    assert [r.confidence for r in got] == [Decimal("0.80"), Decimal("0.70"), Decimal("0.50")]


async def test_retrieve_recent_impacts_respects_lookback(env):
    session, _, _ = env
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    now = datetime.now(timezone.utc)
    fresh_cluster = await _mk_cluster(session, title="Fresh", entity_tickers=[])
    old_cluster = await _mk_cluster(session, title="Old", entity_tickers=[])
    await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id,
        cluster_id=fresh_cluster.id, confidence="0.70", created_at=now - timedelta(days=1),
    )
    await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id,
        cluster_id=old_cluster.id, confidence="0.90", created_at=now - timedelta(days=15),
    )

    got = await retrieve_recent_impacts(
        user_id, pf.id, session=session, lookback_days=7, k=5
    )
    assert len(got) == 1
    assert got[0].cluster_id == fresh_cluster.id


async def test_retrieve_recent_impacts_skips_guardrail_violations(env):
    session, _, _ = env
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    c1 = await _mk_cluster(session, title="a", entity_tickers=[])
    c2 = await _mk_cluster(session, title="b", entity_tickers=[])
    await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id,
        cluster_id=c1.id, confidence="0.90",
        guardrail_violations=[{"stage": "directional", "reason": "buy detected"}],
    )
    await _mk_impact(
        session, user_id=user_id, portfolio_id=pf.id,
        cluster_id=c2.id, confidence="0.50",
    )

    got = await retrieve_recent_impacts(user_id, pf.id, session=session, k=5)
    assert len(got) == 1
    assert got[0].confidence == Decimal("0.50")


async def test_retrieve_recent_impacts_isolates_users(env):
    session, _, _ = env
    alice = uuid.uuid4()
    bob = uuid.uuid4()
    pf_alice = await _mk_portfolio(session, alice)
    pf_bob = await _mk_portfolio(session, bob)
    cluster = await _mk_cluster(session, title="Fed", entity_tickers=[])
    await _mk_impact(
        session, user_id=bob, portfolio_id=pf_bob.id,
        cluster_id=cluster.id, confidence="0.99",
    )

    got = await retrieve_recent_impacts(alice, pf_alice.id, session=session)
    assert got == []


# ---------------------------------------------------------------------------
# retrieve_news
# ---------------------------------------------------------------------------


async def test_retrieve_news_filters_by_user_tickers(env):
    session, news_store, embed = env
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    await _mk_position(session, pf.id, "AAPL")
    aapl_cluster = await _mk_cluster(
        session, title="Fed hikes rates", entity_tickers=["AAPL"]
    )
    await _mk_news_item(
        session,
        cluster=aapl_cluster,
        title="Fed hikes rates",
        body="Fed announcement affects AAPL positioning across the tech sector.",
        news_store=news_store,
        vec=_unit([1.0, 0.0, 0.05]),
    )
    # Non-user-ticker cluster — pharma news; user holds only AAPL.
    pharma_cluster = await _mk_cluster(
        session, title="Pharma news", entity_tickers=["PFE"]
    )
    await _mk_news_item(
        session,
        cluster=pharma_cluster,
        title="Pharma FDA approval",
        body="PFE receives approval.",
        news_store=news_store,
        vec=_unit([0.0, 1.0, 0.0]),
    )

    got = await retrieve_news(
        "Fed rate decision",
        user_id, pf.id,
        session=session, news_store=news_store, embed=embed, k=5,
    )
    assert len(got) == 1
    assert got[0].cluster_id == aapl_cluster.id
    assert "AAPL" in got[0].snippet


async def test_retrieve_news_empty_when_user_has_no_positions(env):
    session, news_store, embed = env
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    # Positions list is empty — nothing to filter to.
    got = await retrieve_news(
        "Fed", user_id, pf.id,
        session=session, news_store=news_store, embed=embed,
    )
    assert got == []


async def test_retrieve_news_min_similarity_filter(env):
    session, news_store, embed = env
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    await _mk_position(session, pf.id, "AAPL")
    cluster = await _mk_cluster(session, title="c", entity_tickers=["AAPL"])
    # Item vector is orthogonal to the query axis → similarity ≈ 0.
    await _mk_news_item(
        session,
        cluster=cluster,
        title="unrelated",
        body="unrelated body",
        news_store=news_store,
        vec=_unit([0.0, 0.0, 1.0]),
    )

    got = await retrieve_news(
        "Fed rate", user_id, pf.id,
        session=session, news_store=news_store, embed=embed,
        min_similarity=0.35,
    )
    assert got == []


async def test_retrieve_news_ordered_by_similarity_desc(env):
    session, news_store, embed = env
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    await _mk_position(session, pf.id, "AAPL")
    cluster = await _mk_cluster(session, title="c", entity_tickers=["AAPL"])
    # Two items: one closely aligned with query, one only partially aligned.
    await _mk_news_item(
        session, cluster=cluster, title="closer", body="closer body",
        news_store=news_store, vec=_unit([1.0, 0.0, 0.0]),  # sim ≈ 1.0
    )
    await _mk_news_item(
        session, cluster=cluster, title="farther", body="farther body",
        news_store=news_store, vec=_unit([1.0, 0.0, 0.9]),  # sim < 1
    )

    got = await retrieve_news(
        "Fed", user_id, pf.id,
        session=session, news_store=news_store, embed=embed, k=2,
        min_similarity=0.4,
    )
    assert len(got) == 2
    assert got[0].similarity >= got[1].similarity
    assert got[0].title == "closer"


async def test_retrieve_news_excludes_items_older_than_since_days(env):
    session, news_store, embed = env
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    await _mk_position(session, pf.id, "AAPL")
    cluster = await _mk_cluster(session, title="c", entity_tickers=["AAPL"])
    old_when = datetime.now(timezone.utc) - timedelta(days=45)
    await _mk_news_item(
        session, cluster=cluster, title="stale AAPL", body="stale body",
        news_store=news_store, vec=_unit([1.0, 0.0, 0.05]),
        published_at=old_when,
    )

    got = await retrieve_news(
        "Fed", user_id, pf.id,
        session=session, news_store=news_store, embed=embed,
        since_days=30,
    )
    assert got == []


# ---------------------------------------------------------------------------
# get_portfolio_summary
# ---------------------------------------------------------------------------


async def test_get_portfolio_summary_happy_path(env):
    session, _, _ = env
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    await _mk_position(session, pf.id, "AAPL")
    await _mk_position(session, pf.id, "NVDA")
    session.add(
        Theme(
            user_id=user_id,
            description="US monetary policy",
            weight=Decimal("0.75"),
        )
    )
    session.add(
        Briefing(
            user_id=user_id,
            portfolio_id=pf.id,
            briefing_date=date.today(),
            structured_content={
                "generated_summary": "Today's briefing summary body.",
                "top_movers": [],
                "watchlist": [],
                "what_would_change_my_thinking": [],
            },
            cited_impact_ids=[],
        )
    )
    await session.commit()

    got = await get_portfolio_summary(user_id, pf.id, session=session)
    assert got is not None
    assert got.portfolio_id == pf.id
    tickers = {p["ticker"] for p in got.positions}
    assert tickers == {"AAPL", "NVDA"}
    assert len(got.themes) == 1
    assert got.themes[0]["description"] == "US monetary policy"
    assert got.latest_briefing_summary == "Today's briefing summary body."
    assert got.latest_briefing_date == date.today()


async def test_get_portfolio_summary_null_briefing_fields_when_absent(env):
    session, _, _ = env
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    got = await get_portfolio_summary(user_id, pf.id, session=session)
    assert got is not None
    assert got.latest_briefing_summary is None
    assert got.latest_briefing_date is None


async def test_get_portfolio_summary_returns_none_for_other_users_portfolio(env):
    session, _, _ = env
    alice = uuid.uuid4()
    bob = uuid.uuid4()
    bob_pf = await _mk_portfolio(session, bob)
    got = await get_portfolio_summary(alice, bob_pf.id, session=session)
    assert got is None
