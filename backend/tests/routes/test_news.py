"""REL-06 acceptance: /api/news/relevant + /api/news/clusters/{id}."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
    NewsCluster,
    NewsItem,
    Portfolio,
    Position,
    RelevanceScore,
    Theme,
)
from app.main import app
from app.utils.auth import UserContext, require_auth

ALICE = uuid.uuid4()
BOB = uuid.uuid4()


def _fake_user_factory(user_id: uuid.UUID):
    async def _fake() -> UserContext:
        return UserContext(user_id=user_id, email=f"{user_id}@test", role="authenticated")

    return _fake


@pytest_asyncio.fixture
async def env() -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
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
        yield c, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass


async def _as_user(user_id: uuid.UUID) -> None:
    app.dependency_overrides[require_auth] = _fake_user_factory(user_id)


async def _seed_portfolio(
    session: AsyncSession, user_id: uuid.UUID, *, active: bool = True, name: str | None = None
) -> Portfolio:
    pf = Portfolio(
        user_id=user_id,
        name=name or f"pf-{uuid.uuid4().hex[:6]}",
        is_active=active,
    )
    session.add(pf)
    await session.commit()
    await session.refresh(pf)
    return pf


async def _seed_cluster(
    session: AsyncSession, *, title: str, last_seen: datetime, item_count: int = 1
) -> NewsCluster:
    cluster = NewsCluster(
        canonical_title=title,
        first_seen_at=last_seen,
        last_seen_at=last_seen,
        entity_tickers=[],
        entity_topics=[],
        member_sources=["newsapi"],
    )
    session.add(cluster)
    await session.flush()
    for i in range(item_count):
        session.add(
            NewsItem(
                cluster_id=cluster.id,
                source="newsapi",
                url=f"https://example.com/{uuid.uuid4().hex[:8]}",
                url_hash=uuid.uuid4().hex,
                title=f"{title} — item {i}",
                body=f"body {i}",
                published_at=last_seen - timedelta(minutes=i),
            )
        )
    await session.commit()
    return cluster


async def _seed_relevance(
    session: AsyncSession,
    *,
    cluster: NewsCluster,
    user_id: uuid.UUID,
    portfolio_id: uuid.UUID,
    score: str,
    stage: str = "classifier",
    touched_positions: list[uuid.UUID] | None = None,
) -> RelevanceScore:
    row = RelevanceScore(
        cluster_id=cluster.id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        score=Decimal(score),
        touched_position_ids=[str(x) for x in (touched_positions or [])],
        touched_theme_ids=[],
        stage=stage,
        rationale=f"mechanism for {score}",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# /api/news/relevant
# ---------------------------------------------------------------------------


async def test_relevant_feed_orders_by_score_desc_then_last_seen_desc(env):
    client, factory = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE, active=True)
        now = datetime.now(timezone.utc)
        older_high = await _seed_cluster(s, title="High-old", last_seen=now - timedelta(hours=2))
        newer_high = await _seed_cluster(s, title="High-new", last_seen=now)
        low_new = await _seed_cluster(s, title="Low-new", last_seen=now)
        await _seed_relevance(s, cluster=older_high, user_id=ALICE, portfolio_id=pf.id, score="0.90")
        await _seed_relevance(s, cluster=newer_high, user_id=ALICE, portfolio_id=pf.id, score="0.90")
        await _seed_relevance(s, cluster=low_new, user_id=ALICE, portfolio_id=pf.id, score="0.20")

    r = await client.get("/api/news/relevant")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 3
    # Same score → newer last_seen wins the tiebreak.
    assert rows[0]["cluster"]["canonical_title"] == "High-new"
    assert rows[1]["cluster"]["canonical_title"] == "High-old"
    # Lower score comes last regardless of freshness.
    assert rows[2]["cluster"]["canonical_title"] == "Low-new"
    # Relevance payload is present per row.
    assert Decimal(str(rows[0]["relevance"]["score"])) == Decimal("0.90")
    assert rows[0]["relevance"]["stage"] == "classifier"


async def test_relevant_feed_respects_limit_and_since(env):
    client, factory = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE, active=True)
        now = datetime.now(timezone.utc)
        for i in range(6):
            c = await _seed_cluster(s, title=f"C{i}", last_seen=now - timedelta(hours=i))
            await _seed_relevance(
                s, cluster=c, user_id=ALICE, portfolio_id=pf.id, score=f"0.{50 + i}"
            )

    r = await client.get("/api/news/relevant?limit=3")
    assert r.status_code == 200
    assert len(r.json()) == 3

    cutoff = datetime.now(timezone.utc) - timedelta(hours=3)
    r = await client.get("/api/news/relevant", params={"since": cutoff.isoformat()})
    assert r.status_code == 200
    body = r.json()
    assert body, "since filter dropped everything — expected some rows within the window"
    # sqlite strips tzinfo on round-trip, so parse response times naive.
    cutoff_naive = cutoff.replace(tzinfo=None)
    for row in body:
        got = datetime.fromisoformat(row["cluster"]["last_seen_at"])
        got = got.replace(tzinfo=None) if got.tzinfo else got
        assert got >= cutoff_naive


async def test_relevant_feed_excludes_other_users_rows(env):
    """Alice's feed must never surface Bob's relevance rows for the same cluster."""
    client, factory = env
    async with factory() as s:
        alice_pf = await _seed_portfolio(s, ALICE, active=True)
        bob_pf = await _seed_portfolio(s, BOB, active=True)
        now = datetime.now(timezone.utc)
        shared_cluster = await _seed_cluster(s, title="Fed", last_seen=now)
        # Bob has a very-high relevance row on the shared cluster.
        await _seed_relevance(
            s, cluster=shared_cluster, user_id=BOB, portfolio_id=bob_pf.id, score="0.99"
        )
        # Alice has none.

    r = await client.get("/api/news/relevant")
    assert r.status_code == 200
    assert r.json() == []  # Alice sees nothing — Bob's row is not hers.

    # Now Alice creates her own row on the same cluster.
    async with factory() as s:
        await _seed_relevance(
            s, cluster=shared_cluster, user_id=ALICE, portfolio_id=alice_pf.id, score="0.30"
        )
    r = await client.get("/api/news/relevant")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert Decimal(str(rows[0]["relevance"]["score"])) == Decimal("0.30")
    assert rows[0]["relevance"]["user_id"] == str(ALICE)


async def test_relevant_feed_uses_active_portfolio_only(env):
    """Alice has an inactive portfolio with a high-score row — it must not surface."""
    client, factory = env
    async with factory() as s:
        active = await _seed_portfolio(s, ALICE, active=True, name="Main")
        inactive = await _seed_portfolio(s, ALICE, active=False, name="Legacy")
        now = datetime.now(timezone.utc)
        c1 = await _seed_cluster(s, title="Active-scored", last_seen=now)
        c2 = await _seed_cluster(s, title="Inactive-scored", last_seen=now)
        await _seed_relevance(
            s, cluster=c1, user_id=ALICE, portfolio_id=active.id, score="0.50"
        )
        await _seed_relevance(
            s, cluster=c2, user_id=ALICE, portfolio_id=inactive.id, score="0.99"
        )

    r = await client.get("/api/news/relevant")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["cluster"]["canonical_title"] == "Active-scored"


async def test_relevant_feed_with_no_active_portfolio_returns_empty(env):
    client, _factory = env  # Alice never created a portfolio.
    r = await client.get("/api/news/relevant")
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# /api/news/clusters/{id}
# ---------------------------------------------------------------------------


async def test_cluster_detail_includes_items_and_caller_relevance(env):
    client, factory = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE, active=True)
        now = datetime.now(timezone.utc)
        cluster = await _seed_cluster(s, title="Fed", last_seen=now, item_count=3)
        rel = await _seed_relevance(
            s, cluster=cluster, user_id=ALICE, portfolio_id=pf.id, score="0.77"
        )

    r = await client.get(f"/api/news/clusters/{cluster.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["cluster"]["id"] == str(cluster.id)
    assert len(body["cluster"]["items"]) == 3
    # Items are ordered newest first.
    published = [datetime.fromisoformat(i["published_at"]) for i in body["cluster"]["items"]]
    assert published == sorted(published, reverse=True)
    assert body["relevance"]["id"] == str(rel.id)
    assert Decimal(str(body["relevance"]["score"])) == Decimal("0.77")
    assert body["impact"] is None


async def test_cluster_detail_relevance_is_null_when_caller_has_no_row(env):
    client, factory = env
    async with factory() as s:
        await _seed_portfolio(s, ALICE, active=True)
        now = datetime.now(timezone.utc)
        cluster = await _seed_cluster(s, title="Fed", last_seen=now)
        # No relevance row for Alice.

    r = await client.get(f"/api/news/clusters/{cluster.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["cluster"]["id"] == str(cluster.id)
    assert body["relevance"] is None


async def test_cluster_detail_never_exposes_another_users_relevance(env):
    """Alice fetches a cluster where only Bob has scored — relevance must be null."""
    client, factory = env
    async with factory() as s:
        bob_pf = await _seed_portfolio(s, BOB, active=True)
        await _seed_portfolio(s, ALICE, active=True)  # Alice has an active pf but no row.
        cluster = await _seed_cluster(
            s, title="Fed", last_seen=datetime.now(timezone.utc)
        )
        await _seed_relevance(
            s, cluster=cluster, user_id=BOB, portfolio_id=bob_pf.id, score="0.95"
        )

    r = await client.get(f"/api/news/clusters/{cluster.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["relevance"] is None


async def test_cluster_detail_404_for_unknown_cluster(env):
    client, _ = env
    r = await client.get(f"/api/news/clusters/{uuid.uuid4()}")
    assert r.status_code == 404
