"""IMP-05 acceptance: /api/news/clusters/{id}/impact + /impact/generate."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
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
    ImpactAssessment,
    NewsCluster,
    NewsItem,
    Portfolio,
    Position,
    RelevanceScore,
    Theme,
)
from app.main import app
from app.routes.impact import EnqueueFn, get_impact_enqueue
from app.utils.auth import UserContext, require_auth

ALICE = uuid.uuid4()
BOB = uuid.uuid4()


def _fake_user_factory(user_id: uuid.UUID):
    async def _fake() -> UserContext:
        return UserContext(
            user_id=user_id, email=f"{user_id}@test", role="authenticated"
        )

    return _fake


class _EnqueueRecorder:
    """Test double for the impact-generation enqueue callable.

    The default enqueue fires an `asyncio.create_task` that builds a real
    `LLMClient` and `EmbeddingClient` — heavy and non-deterministic. Tests
    replace the dependency with an instance of this class so they can:
    - assert the enqueue was (or wasn't) called
    - assert the parameters passed
    - optionally have the enqueue synchronously write a cached row so the
      "poll returns 200" flow can be exercised without touching the graph
    """

    def __init__(
        self,
        *,
        on_call: EnqueueFn | None = None,
    ) -> None:
        self.calls: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID, bool]] = []
        self._on_call = on_call

    async def __call__(
        self,
        cluster_id: uuid.UUID,
        user_id: uuid.UUID,
        portfolio_id: uuid.UUID,
        force: bool,
    ) -> None:
        self.calls.append((cluster_id, user_id, portfolio_id, force))
        if self._on_call is not None:
            await self._on_call(cluster_id, user_id, portfolio_id, force)


@pytest_asyncio.fixture
async def env() -> AsyncIterator[
    tuple[AsyncClient, async_sessionmaker[AsyncSession], _EnqueueRecorder]
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

    enqueue = _EnqueueRecorder()

    app.dependency_overrides[get_db_session] = _session_override
    app.dependency_overrides[require_auth] = _fake_user_factory(ALICE)
    app.dependency_overrides[get_impact_enqueue] = lambda: enqueue

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c, session_factory, enqueue

    app.dependency_overrides.clear()
    await engine.dispose()
    try:
        db_path.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


async def _seed_portfolio(
    session: AsyncSession, user_id: uuid.UUID, *, active: bool = True
) -> Portfolio:
    pf = Portfolio(
        user_id=user_id, name=f"pf-{uuid.uuid4().hex[:6]}", is_active=active
    )
    session.add(pf)
    await session.commit()
    await session.refresh(pf)
    return pf


async def _seed_cluster(
    session: AsyncSession, *, title: str = "Fed hikes 25bps"
) -> NewsCluster:
    now = datetime.now(timezone.utc)
    cluster = NewsCluster(
        canonical_title=title,
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=[],
        entity_topics=[],
        member_sources=["newsapi"],
    )
    session.add(cluster)
    await session.flush()
    session.add(
        NewsItem(
            cluster_id=cluster.id,
            source="newsapi",
            url=f"https://example.com/{uuid.uuid4().hex[:8]}",
            url_hash=uuid.uuid4().hex,
            title=title,
            body=title,
            published_at=now,
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
) -> RelevanceScore:
    row = RelevanceScore(
        cluster_id=cluster.id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        score=Decimal(score),
        touched_position_ids=[],
        touched_theme_ids=[],
        stage="classifier",
        rationale="test",
    )
    session.add(row)
    await session.commit()
    return row


async def _seed_impact(
    session: AsyncSession,
    *,
    cluster: NewsCluster,
    user_id: uuid.UUID,
    portfolio_id: uuid.UUID,
) -> ImpactAssessment:
    row = ImpactAssessment(
        cluster_id=cluster.id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        mechanism=(
            "Higher policy rates compress duration-sensitive equity valuations "
            "via a rising discount rate on future cash flows."
        ),
        magnitude_low=Decimal("-0.05"),
        magnitude_high=Decimal("-0.02"),
        timeframe_days=30,
        confidence=Decimal("0.65"),
        falsifiability="Thesis breaks if the 10y yield curve re-inverts within 5 sessions.",
        citations=[
            {
                "source": "reuters",
                "url": "https://reuters.example/fed",
                "title": "Fed hikes 25bps",
                "quote": "The FOMC raised rates by a quarter point.",
            }
        ],
        historical_analogs=[],
        affected_positions=[str(uuid.uuid4())],
        raw_llm_output="{...}",
        guardrail_violations=[],
        langsmith_run_id=None,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# GET /api/news/clusters/{id}/impact
# ---------------------------------------------------------------------------


async def test_get_returns_cached_impact_200(env):
    client, factory, enqueue = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        cluster = await _seed_cluster(s)
        row = await _seed_impact(
            s, cluster=cluster, user_id=ALICE, portfolio_id=pf.id
        )

    r = await client.get(f"/api/news/clusters/{cluster.id}/impact")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(row.id)
    assert body["mechanism"].startswith("Higher policy rates")
    assert Decimal(str(body["confidence"])) == Decimal("0.65")
    # Cached path must NOT enqueue.
    assert enqueue.calls == []


async def test_get_above_threshold_no_cache_returns_202_and_enqueues(env):
    client, factory, enqueue = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        cluster = await _seed_cluster(s)
        await _seed_relevance(
            s, cluster=cluster, user_id=ALICE, portfolio_id=pf.id, score="0.75"
        )

    r = await client.get(f"/api/news/clusters/{cluster.id}/impact")
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "generating"
    assert body["poll_url"].endswith(f"/api/news/clusters/{cluster.id}/impact")
    assert len(enqueue.calls) == 1
    cid, uid, pid, force = enqueue.calls[0]
    assert cid == cluster.id
    assert uid == ALICE
    assert pid == pf.id
    assert force is False


async def test_get_below_threshold_returns_404(env):
    client, factory, enqueue = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        cluster = await _seed_cluster(s)
        await _seed_relevance(
            s, cluster=cluster, user_id=ALICE, portfolio_id=pf.id, score="0.20"
        )

    r = await client.get(f"/api/news/clusters/{cluster.id}/impact")
    assert r.status_code == 404, r.text
    assert "threshold" in r.text.lower()
    assert enqueue.calls == []


async def test_get_no_relevance_row_returns_404(env):
    client, factory, enqueue = env
    async with factory() as s:
        await _seed_portfolio(s, ALICE)
        cluster = await _seed_cluster(s)

    r = await client.get(f"/api/news/clusters/{cluster.id}/impact")
    assert r.status_code == 404, r.text
    assert enqueue.calls == []


async def test_get_no_active_portfolio_returns_404(env):
    client, factory, enqueue = env
    async with factory() as s:
        cluster = await _seed_cluster(s)  # Alice has no portfolio at all.

    r = await client.get(f"/api/news/clusters/{cluster.id}/impact")
    assert r.status_code == 404
    assert enqueue.calls == []


async def test_get_unknown_cluster_returns_404(env):
    client, factory, enqueue = env
    async with factory() as s:
        await _seed_portfolio(s, ALICE)

    r = await client.get(f"/api/news/clusters/{uuid.uuid4()}/impact")
    assert r.status_code == 404
    assert enqueue.calls == []


async def test_get_never_exposes_another_users_impact(env):
    """Alice fetches; only Bob has a cached impact row. Should behave as if no cache."""
    client, factory, enqueue = env
    async with factory() as s:
        pf_alice = await _seed_portfolio(s, ALICE)
        pf_bob = await _seed_portfolio(s, BOB)
        cluster = await _seed_cluster(s)
        # Alice has a high-score relevance row → will trigger enqueue.
        await _seed_relevance(
            s,
            cluster=cluster,
            user_id=ALICE,
            portfolio_id=pf_alice.id,
            score="0.90",
        )
        # Bob has a cached impact — irrelevant to Alice's view.
        await _seed_impact(
            s, cluster=cluster, user_id=BOB, portfolio_id=pf_bob.id
        )

    r = await client.get(f"/api/news/clusters/{cluster.id}/impact")
    assert r.status_code == 202
    assert len(enqueue.calls) == 1


# ---------------------------------------------------------------------------
# POST /api/news/clusters/{id}/impact/generate
# ---------------------------------------------------------------------------


async def test_post_generate_always_enqueues_with_force_true(env):
    """Even when a cached row exists, POST /impact/generate re-runs (force=True)."""
    client, factory, enqueue = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        cluster = await _seed_cluster(s)
        await _seed_relevance(
            s, cluster=cluster, user_id=ALICE, portfolio_id=pf.id, score="0.75"
        )
        # Cached row exists — GET would return 200. POST should still enqueue.
        await _seed_impact(
            s, cluster=cluster, user_id=ALICE, portfolio_id=pf.id
        )

    r = await client.post(f"/api/news/clusters/{cluster.id}/impact/generate")
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "generating"
    assert len(enqueue.calls) == 1
    _, _, _, force = enqueue.calls[0]
    assert force is True


async def test_post_generate_below_threshold_returns_404(env):
    client, factory, enqueue = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        cluster = await _seed_cluster(s)
        await _seed_relevance(
            s, cluster=cluster, user_id=ALICE, portfolio_id=pf.id, score="0.10"
        )

    r = await client.post(f"/api/news/clusters/{cluster.id}/impact/generate")
    assert r.status_code == 404
    assert enqueue.calls == []


# ---------------------------------------------------------------------------
# ClusterDetailRead.impact is now typed and populated
# ---------------------------------------------------------------------------


async def test_cluster_detail_serializes_impact_row(env):
    """REL-06's /clusters/{id} endpoint now returns a real ImpactRead body."""
    client, factory, _ = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        cluster = await _seed_cluster(s)
        row = await _seed_impact(
            s, cluster=cluster, user_id=ALICE, portfolio_id=pf.id
        )

    r = await client.get(f"/api/news/clusters/{cluster.id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["impact"] is not None
    assert body["impact"]["id"] == str(row.id)
    assert body["impact"]["mechanism"].startswith("Higher policy rates")


async def test_cluster_detail_impact_null_when_caller_has_no_row(env):
    client, factory, _ = env
    async with factory() as s:
        pf = await _seed_portfolio(s, ALICE)
        cluster = await _seed_cluster(s)
        # No impact row for Alice; Bob has one.
        pf_bob = await _seed_portfolio(s, BOB)
        await _seed_impact(
            s, cluster=cluster, user_id=BOB, portfolio_id=pf_bob.id
        )
        assert pf.id != pf_bob.id  # sanity

    r = await client.get(f"/api/news/clusters/{cluster.id}")
    assert r.status_code == 200
    assert r.json()["impact"] is None
