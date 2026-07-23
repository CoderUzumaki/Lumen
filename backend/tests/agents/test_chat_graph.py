"""CHAT-03 acceptance: chat-agent LangGraph.

Hermetic — sqlite tempfile + Chroma tempdir, scripted LLM double, fake
deterministic embeddings. Mirrors `tests/agents/test_impact_graph.py`'s
`_ScriptedLLM` pattern and `tests/agents/test_relevance_prefilter.py`'s
env fixture.
"""
from __future__ import annotations

import json
import math
import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
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
from app.agents.chat.graph import (
    CHAT_GRAPH,
    _ChatDraft,
    _IntentClassification,
    _ToolPlan,
    run_chat_turn,
)
from app.db.base import Base
from app.db.models import (  # noqa: F401 register with Base.metadata
    ChatMessage,
    ChatSession,
    NewsCluster,
    NewsItem,
    Portfolio,
    Position,
)
from app.schemas.impact import Citation
from app.utils.embeddings import EmbeddingClient
from app.utils.llm import LLMClient, LLMResponse


# --- doubles ---------------------------------------------------------------


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class _FakeEmbed(EmbeddingClient):
    """Deterministic embedding: all inputs collapse to axis 0."""

    async def embed(self, texts):  # type: ignore[override]
        return [_unit([1.0, 0.0, 0.05]) for _ in texts]


class _ScriptedLLM(LLMClient):
    """Return responses from a queue; pass an Exception to make `.complete()` raise.

    Pattern lifted from `tests/agents/test_impact_graph.py`. Each pushed item
    is either a Pydantic instance (returned as `parsed`) or a plain payload
    that gets `json.dumps`'d.
    """

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
        if isinstance(payload, Exception):
            raise payload
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
async def env() -> AsyncIterator[
    tuple[AsyncSession, vs.VectorStore, EmbeddingClient]
]:
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    chroma_path = Path(tempfile.mkdtemp(prefix="lumen-chat-chroma-"))
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


# --- seeding helpers -------------------------------------------------------


_SEED_NEWS_URL = "https://example.com/fed-hikes"
_SEED_NEWS_TITLE = "Fed raises target rate 25bps"
_SEED_NEWS_BODY = (
    "The Federal Reserve raised the federal funds rate by 25 basis points. "
    "Chair Powell noted duration-sensitive equity multiples typically compress "
    "when policy rates rise, with AAPL and NVDA cited as archetypes."
)
_SEED_QUOTE = "duration-sensitive equity multiples typically compress"


async def _seed_session_and_portfolio(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    active_ticker: str = "AAPL",
) -> tuple[ChatSession, Portfolio, Position]:
    portfolio = Portfolio(
        user_id=user_id,
        name=f"pf-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    session.add(portfolio)
    await session.flush()

    position = Position(
        portfolio_id=portfolio.id,
        ticker=active_ticker,
        asset_type="equity",
        currency="USD",
        exchange="NASDAQ",
    )
    session.add(position)
    await session.flush()

    chat_session = ChatSession(
        user_id=user_id,
        portfolio_id=portfolio.id,
        title="test chat",
    )
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)
    return chat_session, portfolio, position


async def _seed_news(
    session: AsyncSession,
    news_store: vs.VectorStore,
    *,
    tickers: list[str],
) -> NewsItem:
    now = datetime.now(timezone.utc)
    cluster = NewsCluster(
        canonical_title=_SEED_NEWS_TITLE,
        first_seen_at=now,
        last_seen_at=now,
        entity_tickers=tickers,
        entity_topics=["rates"],
        member_sources=["newsapi"],
    )
    session.add(cluster)
    await session.flush()

    item = NewsItem(
        cluster_id=cluster.id,
        source="newsapi",
        url=_SEED_NEWS_URL,
        url_hash=uuid.uuid4().hex,
        title=_SEED_NEWS_TITLE,
        body=_SEED_NEWS_BODY,
        published_at=now,
    )
    session.add(item)
    await session.commit()

    news_store.upsert(
        ids=[str(item.id)],
        embeddings=[_unit([1.0, 0.0, 0.05])],
        metadatas=[
            {
                "cluster_id": str(cluster.id),
                "source": "newsapi",
                "published_at_iso": now.isoformat(),
            }
        ],
        documents=[_SEED_NEWS_TITLE],
    )
    return item


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_graph_compiles_at_import():
    assert CHAT_GRAPH is not None
    assert hasattr(CHAT_GRAPH, "ainvoke")


@pytest.mark.asyncio
async def test_out_of_scope_returns_polite_refusal(env):
    session, news_store, embed = env
    user_id = uuid.uuid4()
    chat_session, _, _ = await _seed_session_and_portfolio(session, user_id=user_id)

    # Trigger lexical scope hit — "should i file" is in the tax patterns.
    llm = _ScriptedLLM([])

    row = await run_chat_turn(
        chat_session.id,
        user_id,
        "Should I file a Roth conversion for tax reasons?",
        session=session,
        llm=llm,
        news_store=news_store,
        embed=embed,
    )

    assert row.role == "assistant"
    assert "tax" in row.content.lower()
    assert row.citations in ([], None)
    # Scope pre-check is lexical-only (skip_llm=True); no LLM calls at all.
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_portfolio_context_question_calls_portfolio_summary_tool(env):
    session, news_store, embed = env
    user_id = uuid.uuid4()
    chat_session, portfolio, position = await _seed_session_and_portfolio(
        session, user_id=user_id, active_ticker="AAPL"
    )

    intent = _IntentClassification(label="portfolio-context", rationale="asks about own positions")
    plan = _ToolPlan(use_portfolio_summary=True)
    draft = _ChatDraft(
        content=(
            f"Your active portfolio {portfolio.name} holds AAPL as its "
            "single equity position; that is the position most exposed to the "
            "rate transmission channel described in the context."
        ),
        citations=[],
    )
    llm = _ScriptedLLM([intent, plan, draft])

    row = await run_chat_turn(
        chat_session.id,
        user_id,
        "What's my biggest position?",
        session=session,
        llm=llm,
        news_store=news_store,
        embed=embed,
    )

    assert row.role == "assistant"
    assert "AAPL" in row.content
    assert llm.calls == 3
    _ = position  # silence "unused" — the ticker check above is the meaningful assertion


@pytest.mark.asyncio
async def test_news_question_retrieves_news_and_cites(env):
    session, news_store, embed = env
    user_id = uuid.uuid4()
    chat_session, _, _ = await _seed_session_and_portfolio(
        session, user_id=user_id, active_ticker="AAPL"
    )
    await _seed_news(session, news_store, tickers=["AAPL"])

    intent = _IntentClassification(label="news-question", rationale="asks about news")
    plan = _ToolPlan(use_news=True, news_query="Fed rate hike")
    draft = _ChatDraft(
        content=(
            "Recent reporting notes that duration-sensitive equity multiples "
            "typically compress in response to policy tightening."
        ),
        citations=[
            Citation(
                source="newsapi",
                url=_SEED_NEWS_URL,  # type: ignore[arg-type]
                title=_SEED_NEWS_TITLE,
                quote=_SEED_QUOTE,
            )
        ],
    )
    llm = _ScriptedLLM([intent, plan, draft])

    row = await run_chat_turn(
        chat_session.id,
        user_id,
        "What happened to the Fed today?",
        session=session,
        llm=llm,
        news_store=news_store,
        embed=embed,
    )

    assert row.role == "assistant"
    assert row.citations is not None
    assert len(row.citations) >= 1
    assert row.citations[0]["url"].startswith(_SEED_NEWS_URL)
    # GRD-02 accepted the citation; no violations recorded.
    assert row.guardrail_violations == []
    assert llm.calls == 3


@pytest.mark.asyncio
async def test_guardrail_violation_replaces_content_with_refusal(env):
    session, news_store, embed = env
    user_id = uuid.uuid4()
    chat_session, _, _ = await _seed_session_and_portfolio(
        session, user_id=user_id, active_ticker="AAPL"
    )

    intent = _IntentClassification(label="mechanism-question", rationale="")
    plan = _ToolPlan(use_portfolio_summary=True)
    # Compose returns directional text — GRD-01 lexical will reject.
    draft = _ChatDraft(
        content="You should buy TLT as a hedge against rate risk.",
        citations=[],
    )
    llm = _ScriptedLLM([intent, plan, draft])

    row = await run_chat_turn(
        chat_session.id,
        user_id,
        "How should I think about duration risk?",
        session=session,
        llm=llm,
        news_store=news_store,
        embed=embed,
    )

    assert row.role == "assistant"
    assert "policy check" in row.content
    assert row.citations in ([], None)
    assert row.guardrail_violations is not None
    assert any(v.get("stage") == "directional" for v in row.guardrail_violations)


@pytest.mark.asyncio
async def test_persists_user_and_assistant_rows(env):
    session, news_store, embed = env
    user_id = uuid.uuid4()
    chat_session, _, _ = await _seed_session_and_portfolio(
        session, user_id=user_id, active_ticker="AAPL"
    )

    original_updated_at = chat_session.updated_at

    intent = _IntentClassification(label="mechanism-question", rationale="")
    plan = _ToolPlan(use_portfolio_summary=True)
    draft = _ChatDraft(
        content=(
            "Duration risk is the mechanism through which higher discount "
            "rates compress multiples on distant-horizon cash flows."
        ),
        citations=[],
    )
    llm = _ScriptedLLM([intent, plan, draft])

    await run_chat_turn(
        chat_session.id,
        user_id,
        "Explain duration risk.",
        session=session,
        llm=llm,
        news_store=news_store,
        embed=embed,
    )

    rows = list(
        (
            await session.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == chat_session.id)
                .order_by(ChatMessage.created_at)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert rows[0].role == "user"
    assert rows[0].content == "Explain duration risk."
    assert rows[1].role == "assistant"
    assert rows[1].content.startswith("Duration risk")

    # updated_at was bumped via the explicit UPDATE in _persist_message_node.
    refreshed = (
        await session.execute(
            select(ChatSession).where(ChatSession.id == chat_session.id)
        )
    ).scalar_one()
    assert refreshed.updated_at >= original_updated_at


@pytest.mark.asyncio
async def test_cross_user_session_raises(env):
    session, news_store, embed = env
    alice = uuid.uuid4()
    bob = uuid.uuid4()
    alice_chat, _, _ = await _seed_session_and_portfolio(session, user_id=alice)

    llm = _ScriptedLLM([])

    with pytest.raises(PermissionError):
        await run_chat_turn(
            alice_chat.id,
            bob,
            "peeking at Alice's session",
            session=session,
            llm=llm,
            news_store=news_store,
            embed=embed,
        )
    # Nothing should have been persisted under the session.
    rows = list(
        (
            await session.execute(
                select(ChatMessage).where(ChatMessage.session_id == alice_chat.id)
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


@pytest.mark.asyncio
async def test_llm_failure_persists_fallback_message(env):
    session, news_store, embed = env
    user_id = uuid.uuid4()
    chat_session, _, _ = await _seed_session_and_portfolio(
        session, user_id=user_id, active_ticker="AAPL"
    )

    intent = _IntentClassification(label="mechanism-question", rationale="")
    plan = _ToolPlan(use_portfolio_summary=True)
    # Third call — compose_response — raises.
    llm = _ScriptedLLM([intent, plan, RuntimeError("upstream 500")])

    row = await run_chat_turn(
        chat_session.id,
        user_id,
        "Tell me about the market.",
        session=session,
        llm=llm,
        news_store=news_store,
        embed=embed,
    )

    assert row.role == "assistant"
    assert "couldn't generate" in row.content
    assert row.guardrail_violations is not None
    assert any(v.get("stage") == "llm" for v in row.guardrail_violations)
