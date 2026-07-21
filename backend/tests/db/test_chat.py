"""CHAT-01 acceptance: chat_sessions + chat_messages schema + Pydantic wire types."""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.db.models import (  # noqa: F401 register with Base.metadata
    ChatMessage,
    ChatSession,
    NewsCluster,
    Portfolio,
)
from app.schemas.chat import ChatMessageIn


# --- Fixtures ---------------------------------------------------------------


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Fresh sqlite via create_all() — fast; doesn't exercise migration DDL."""
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


async def _mk_cluster(session: AsyncSession) -> NewsCluster:
    now = datetime.now(timezone.utc)
    cluster = NewsCluster(
        canonical_title="Fed hikes",
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=["SPY"],
        entity_topics=[],
        member_sources=["newsapi"],
    )
    session.add(cluster)
    await session.flush()
    return cluster


async def _mk_portfolio(session: AsyncSession, user_id: uuid.UUID) -> Portfolio:
    p = Portfolio(user_id=user_id, name=f"pf-{uuid.uuid4().hex[:6]}", is_active=True)
    session.add(p)
    await session.flush()
    return p


async def _mk_session(
    db_session: AsyncSession,
    user_id: uuid.UUID,
    portfolio: Portfolio,
    seed_cluster_id: uuid.UUID | None = None,
) -> ChatSession:
    cs = ChatSession(
        user_id=user_id,
        portfolio_id=portfolio.id,
        title="thesis on rates",
        seed_cluster_id=seed_cluster_id,
    )
    db_session.add(cs)
    await db_session.flush()
    return cs


# --- ORM roundtrip ----------------------------------------------------------


async def test_insert_session_and_messages(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    cs = await _mk_session(session, user_id, pf)

    session.add_all(
        [
            ChatMessage(
                session_id=cs.id,
                role="user",
                content="What's the impact of the Fed hike on my portfolio?",
                citations=[],
                guardrail_violations=[],
            ),
            ChatMessage(
                session_id=cs.id,
                role="assistant",
                content="Higher rates typically compress duration-sensitive equity valuations.",
                citations=[
                    {
                        "source": "reuters",
                        "url": "https://reuters.example/x",
                        "title": "Fed decision",
                        "quote": "The Fed raised rates by 25bps.",
                    }
                ],
                tokens_used=142,
                langsmith_run_id="run_abc123",
                guardrail_violations=[],
            ),
        ]
    )
    await session.commit()

    got_session = (
        await session.execute(select(ChatSession).where(ChatSession.id == cs.id))
    ).scalar_one()
    assert got_session.title == "thesis on rates"
    assert got_session.portfolio_id == pf.id
    assert got_session.created_at is not None
    assert got_session.updated_at is not None

    msgs = (
        (
            await session.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == cs.id)
                .order_by(ChatMessage.created_at)
            )
        )
        .scalars()
        .all()
    )
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[1].role == "assistant"
    assert msgs[1].tokens_used == 142
    assert msgs[1].langsmith_run_id == "run_abc123"
    assert msgs[1].citations[0]["source"] == "reuters"


async def test_role_check_constraint_rejects_bad_role(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    cs = await _mk_session(session, user_id, pf)

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                ChatMessage(
                    session_id=cs.id,
                    role="tool",  # not in the allowed set
                    content="hi",
                )
            )
            await session.flush()


async def test_session_delete_cascades_to_messages(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    cs = await _mk_session(session, user_id, pf)
    session.add_all(
        [
            ChatMessage(session_id=cs.id, role="user", content="q1"),
            ChatMessage(session_id=cs.id, role="assistant", content="a1"),
        ]
    )
    await session.commit()

    await session.delete(cs)
    await session.commit()
    session.expire_all()

    assert (await session.execute(select(ChatMessage))).scalars().all() == []
    assert (await session.execute(select(ChatSession))).scalars().all() == []


async def test_portfolio_delete_cascades_to_sessions(session: AsyncSession):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    cs = await _mk_session(session, user_id, pf)
    session.add(ChatMessage(session_id=cs.id, role="user", content="hi"))
    await session.commit()

    await session.delete(pf)
    await session.commit()
    session.expire_all()

    assert (await session.execute(select(ChatSession))).scalars().all() == []
    # And messages under the deleted session are gone too (transitive cascade).
    assert (await session.execute(select(ChatMessage))).scalars().all() == []


async def test_seed_cluster_fk_accepts_real_cluster_and_rejects_random(
    session: AsyncSession,
):
    user_id = uuid.uuid4()
    pf = await _mk_portfolio(session, user_id)
    cluster = await _mk_cluster(session)

    # Real cluster: accepted.
    cs = await _mk_session(session, user_id, pf, seed_cluster_id=cluster.id)
    await session.commit()
    assert cs.seed_cluster_id == cluster.id

    # Random UUID: rejected by FK.
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                ChatSession(
                    user_id=user_id,
                    portfolio_id=pf.id,
                    seed_cluster_id=uuid.uuid4(),
                )
            )
            await session.flush()


# --- Migration head ---------------------------------------------------------


def test_migration_head_is_chat(tmp_path, monkeypatch):
    """Full alembic chain to head on a fresh sqlite lands on this revision.

    env.py resolves the DB URL from the `DATABASE_URL` env var (or
    `Config.DATABASE_URL`), not from `alembic_cfg.set_main_option`.

    Side effect: env.py calls `fileConfig(alembic.ini)`, which disables every
    already-created named logger. Re-enable everything after to keep the side
    effect scoped (see tests/db/test_impact.py).
    """
    import logging

    db_path = tmp_path / "chat01.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)

    alembic_cfg = AlembicConfig(
        str(Path(__file__).resolve().parents[2] / "alembic.ini")
    )
    command.upgrade(alembic_cfg, "head")
    for name in list(logging.root.manager.loggerDict):
        logging.getLogger(name).disabled = False

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            assert version == "e5b02c8f6a39"
    finally:
        engine.dispose()


# --- Pydantic wire-shape validation ----------------------------------------


def test_chat_message_in_content_min_length():
    with pytest.raises(ValidationError):
        ChatMessageIn(content="")


def test_chat_message_in_content_max_length():
    ok = ChatMessageIn(content="x" * 4000)
    assert len(ok.content) == 4000
    with pytest.raises(ValidationError):
        ChatMessageIn(content="x" * 4001)
