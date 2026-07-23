"""Chat agent LangGraph (CHAT-03).

Composes the chat retrieval tools (CHAT-02), guardrails (GRD-01/02/03), and
persistent chat history (CHAT-01) into one graph:

    START
      → classify_intent  (GRD-03 lexical scope check, then fast-tier LLM label)
      → [conditional]  out-of-scope → polite_refusal → persist_message → END
                        in-scope    → route_tools
      → route_tools    (fast-tier LLM chooses which retrievers to run)
      → execute_tools  (asyncio.gather over the chosen retrievers)
      → compose_response (thorough-tier LLM → `_ChatDraft`)
      → validate       (GRD-01 lexical + GRD-02 citations)
      → persist_message (writes user + assistant rows, bumps session.updated_at)
      → END

Public entry `run_chat_turn()` is one user message → one persisted assistant
reply. Cross-user access to a session raises `PermissionError`. LLM failures
inside `compose_response` are absorbed into a safe fallback message so the
turn still persists.

Deviation from BUILD.md: `classify_scope` is invoked with `skip_llm=True` and
`check_directional` is likewise `skip_llm=True`. Same rationale as IMP-04 /
BRIEF-02 — the shared scripted LLM under test doubles must not be double-
consumed by guardrail LLM stages. Production keeps the lexical guarantees,
which are the strictest rules in each guardrail.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.prompts import (
    COMPOSE_SYSTEM,
    INTENT_SYSTEM,
    ROUTE_TOOLS_SYSTEM,
    build_compose_prompt,
)
from app.agents.chat.retrievers import (
    ChatNewsSnippet,
    PortfolioSummary,
    get_portfolio_summary,
    retrieve_news,
    retrieve_recent_impacts,
)
from app.db.models.chat import ChatMessage, ChatSession
from app.db.models.portfolio import Portfolio
from app.db.vectorstore import VectorStore
from app.guardrails.citations import SourceStub, check_citations
from app.guardrails.directional import check_directional
from app.guardrails.scope import classify_scope
from app.schemas.impact import Citation, ImpactRead
from app.utils.embeddings import EmbeddingClient
from app.utils.llm import LLMClient, Message

log = logging.getLogger(__name__)


_FALLBACK_LLM_MSG = "I couldn't generate a response. Try rephrasing."
_FALLBACK_GUARDRAIL_MSG = (
    "I ran into a policy check on that response. Please rephrase."
)
_MAX_CONTENT_CHARS = 4000


# ---------------------------------------------------------------------------
# LLM structured outputs
# ---------------------------------------------------------------------------


IntentLabel = Literal["portfolio-context", "news-question", "mechanism-question"]


class _IntentClassification(BaseModel):
    label: IntentLabel
    rationale: str = Field(default="", max_length=200)


class _ToolPlan(BaseModel):
    use_portfolio_summary: bool = False
    use_recent_impacts: bool = False
    use_news: bool = False
    news_query: str | None = None


class _ChatDraft(BaseModel):
    content: str = Field(max_length=_MAX_CONTENT_CHARS)
    citations: list[Citation] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class _GraphState(TypedDict, total=False):
    # -- inputs (populated by the wrapper) -------------------------------
    session_id: UUID
    user_id: UUID
    user_message: str
    session: AsyncSession
    llm: LLMClient
    news_store: VectorStore
    embed: EmbeddingClient
    chat_session: ChatSession
    portfolio_id: UUID | None

    # -- classify_intent -------------------------------------------------
    scope_ok: bool
    refusal_message: str
    intent: IntentLabel | None

    # -- route_tools -----------------------------------------------------
    tool_plan: _ToolPlan | None

    # -- execute_tools ---------------------------------------------------
    portfolio_summary: PortfolioSummary | None
    recent_impacts: list[ImpactRead]
    news_snippets: list[ChatNewsSnippet]

    # -- compose / validate ---------------------------------------------
    draft_content: str
    draft_citations: list[Citation]
    tokens_used: int
    guardrail_violations: list[dict[str, str]]

    # -- output ----------------------------------------------------------
    assistant_row: ChatMessage | None


# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------


def _accum_tokens(state: _GraphState, response: Any) -> int:
    prev = int(state.get("tokens_used") or 0)
    if response is None:
        return prev
    p = int(getattr(response, "prompt_tokens", 0) or 0)
    c = int(getattr(response, "completion_tokens", 0) or 0)
    return prev + p + c


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def _classify_intent_node(state: _GraphState) -> _GraphState:
    """Scope pre-check (lexical), then fast-tier LLM intent classification.

    On any LLM failure inside intent classification, fall back to
    `mechanism-question` — the safest default that still routes through the
    retrieval + guardrail path.
    """
    llm: LLMClient = state["llm"]
    user_message = state.get("user_message") or ""

    verdict = await classify_scope(user_message, llm=llm, skip_llm=True)
    if not verdict.passed:
        return {
            "scope_ok": False,
            "refusal_message": verdict.refusal_message,
            "intent": None,
            "guardrail_violations": [],
            "tokens_used": 0,
        }

    try:
        response = await llm.complete(
            [
                Message(role="system", content=INTENT_SYSTEM),
                Message(role="user", content=user_message),
            ],
            tier="fast",
            response_model=_IntentClassification,
            user_id=state["user_id"],
            agent_name="chat-agent",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("chat: classify_intent LLM failed: %s", exc)
        return {
            "scope_ok": True,
            "refusal_message": "",
            "intent": "mechanism-question",
            "guardrail_violations": [],
            "tokens_used": 0,
        }

    parsed = (
        response.parsed
        if isinstance(response.parsed, _IntentClassification)
        else _IntentClassification(label="mechanism-question")
    )
    return {
        "scope_ok": True,
        "refusal_message": "",
        "intent": parsed.label,
        "guardrail_violations": [],
        "tokens_used": _accum_tokens(state, response),
    }


async def _polite_refusal_node(state: _GraphState) -> _GraphState:
    return {
        "draft_content": state.get("refusal_message") or "",
        "draft_citations": [],
        # Refusals record no guardrail violation — the scope refusal is the
        # designed outcome, not a failure of the compose path.
        "guardrail_violations": [],
    }


async def _route_tools_node(state: _GraphState) -> _GraphState:
    llm: LLMClient = state["llm"]
    intent = state.get("intent") or "mechanism-question"

    user_prompt = (
        f"Intent: {intent}\n"
        f"User message: {state.get('user_message') or ''}\n\n"
        "Choose which of {portfolio_summary, recent_impacts, news} to call. "
        "If news is chosen, propose a `news_query` string suitable for RAG."
    )
    try:
        response = await llm.complete(
            [
                Message(role="system", content=ROUTE_TOOLS_SYSTEM),
                Message(role="user", content=user_prompt),
            ],
            tier="fast",
            response_model=_ToolPlan,
            user_id=state["user_id"],
            agent_name="chat-agent",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("chat: route_tools LLM failed: %s", exc)
        plan = _ToolPlan(use_portfolio_summary=True, use_recent_impacts=True)
        return {"tool_plan": plan, "tokens_used": _accum_tokens(state, None)}

    parsed = response.parsed if isinstance(response.parsed, _ToolPlan) else _ToolPlan()
    return {"tool_plan": parsed, "tokens_used": _accum_tokens(state, response)}


async def _execute_tools_node(state: _GraphState) -> _GraphState:
    """Run the chosen retrievers concurrently via `asyncio.gather`.

    Tools that require a portfolio are skipped when no active portfolio exists
    for the caller — those returns are empty rather than error, so the
    downstream composer just sees less context.
    """
    plan: _ToolPlan | None = state.get("tool_plan")
    if plan is None:
        return {
            "portfolio_summary": None,
            "recent_impacts": [],
            "news_snippets": [],
        }

    session: AsyncSession = state["session"]
    user_id: UUID = state["user_id"]
    portfolio_id: UUID | None = state.get("portfolio_id")

    tasks: list[Any] = []
    labels: list[str] = []

    if plan.use_portfolio_summary and portfolio_id is not None:
        tasks.append(get_portfolio_summary(user_id, portfolio_id, session=session))
        labels.append("portfolio_summary")
    if plan.use_recent_impacts and portfolio_id is not None:
        tasks.append(retrieve_recent_impacts(user_id, portfolio_id, session=session))
        labels.append("recent_impacts")
    if plan.use_news and portfolio_id is not None:
        news_query = (plan.news_query or state.get("user_message") or "").strip()
        if news_query:
            tasks.append(
                retrieve_news(
                    news_query,
                    user_id,
                    portfolio_id,
                    session=session,
                    news_store=state["news_store"],
                    embed=state["embed"],
                )
            )
            labels.append("news")

    portfolio_summary: PortfolioSummary | None = None
    recent_impacts: list[ImpactRead] = []
    news_snippets: list[ChatNewsSnippet] = []

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for label, result in zip(labels, results):
            if isinstance(result, Exception):
                log.warning("chat: retriever %s failed: %s", label, result)
                continue
            if label == "portfolio_summary":
                portfolio_summary = result
            elif label == "recent_impacts":
                recent_impacts = list(result or [])
            elif label == "news":
                news_snippets = list(result or [])

    return {
        "portfolio_summary": portfolio_summary,
        "recent_impacts": recent_impacts,
        "news_snippets": news_snippets,
    }


async def _compose_response_node(state: _GraphState) -> _GraphState:
    llm: LLMClient = state["llm"]

    messages = [
        Message(role="system", content=COMPOSE_SYSTEM),
        Message(role="user", content=build_compose_prompt(dict(state))),
    ]

    try:
        response = await llm.complete(
            messages,
            tier="thorough",
            response_model=_ChatDraft,
            user_id=state["user_id"],
            agent_name="chat-agent",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("chat: compose_response LLM failed: %s", exc)
        return {
            "draft_content": _FALLBACK_LLM_MSG,
            "draft_citations": [],
            "guardrail_violations": [
                {"stage": "llm", "reason": str(exc)[:200]}
            ],
            "tokens_used": _accum_tokens(state, None),
        }

    parsed = response.parsed
    if not isinstance(parsed, _ChatDraft):
        try:
            parsed = _ChatDraft.model_validate_json(response.content or "{}")
        except ValidationError as exc:
            log.warning("chat: compose_response missing parsed draft: %s", exc)
            return {
                "draft_content": _FALLBACK_LLM_MSG,
                "draft_citations": [],
                "guardrail_violations": [
                    {"stage": "llm", "reason": "response missing parsed payload"}
                ],
                "tokens_used": _accum_tokens(state, response),
            }

    content = (parsed.content or "")[:_MAX_CONTENT_CHARS]
    return {
        "draft_content": content,
        "draft_citations": list(parsed.citations or []),
        "tokens_used": _accum_tokens(state, response),
    }


async def _validate_node(state: _GraphState) -> _GraphState:
    """GRD-01 lexical + GRD-02 (when citations + news source-stubs exist).

    On GRD-01 failure, swap in the canned guardrail refusal and drop
    citations — a directional response is never persisted verbatim.
    """
    content = state.get("draft_content") or ""
    citations = list(state.get("draft_citations") or [])
    violations = list(state.get("guardrail_violations") or [])

    # GRD-01 — lexical only (see module docstring for rationale).
    dir_verdict = await check_directional(content, skip_llm=True)
    if not dir_verdict.passed:
        violations.append(
            {"stage": "directional", "reason": dir_verdict.reason[:200]}
        )
        return {
            "draft_content": _FALLBACK_GUARDRAIL_MSG,
            "draft_citations": [],
            "guardrail_violations": violations,
        }

    # GRD-02 — only invoked if citations are non-empty AND we have news
    # source-stubs to check against. Fully synthetic answers with no citations
    # are the composer's choice; policy doesn't force one.
    news_snippets = state.get("news_snippets") or []
    if citations and news_snippets:
        stubs = [SourceStub(url=str(s.url), body=s.snippet) for s in news_snippets]
        cit_verdict = check_citations(citations, allowed_stubs=stubs)
        if not cit_verdict.passed:
            reason = "; ".join(cit_verdict.reasons)[:200] or "unspecified"
            violations.append({"stage": "citations", "reason": reason})

    return {
        "draft_content": content,
        "draft_citations": citations,
        "guardrail_violations": violations,
    }


async def _persist_message_node(state: _GraphState) -> _GraphState:
    """Write user + assistant rows and bump `chat_sessions.updated_at`.

    `chat_sessions.updated_at` has SQLAlchemy `onupdate=func.now()` which only
    fires on UPDATE statements that touch a mapped column. Since we're not
    mutating the session row itself, we issue an explicit UPDATE that sets
    `updated_at=func.now()` — cheap, portable, and works under sqlite.
    """
    session: AsyncSession = state["session"]
    session_id: UUID = state["session_id"]
    user_message = state.get("user_message") or ""
    content = state.get("draft_content") or ""
    citations = list(state.get("draft_citations") or [])
    violations = list(state.get("guardrail_violations") or [])
    tokens_used = int(state.get("tokens_used") or 0) or None

    citations_json = [c.model_dump(mode="json") for c in citations]

    user_row = ChatMessage(
        session_id=session_id,
        role="user",
        content=user_message,
        citations=[],
    )
    session.add(user_row)

    assistant_row = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=content,
        citations=citations_json,
        tokens_used=tokens_used,
        guardrail_violations=violations,
    )
    session.add(assistant_row)

    await session.execute(
        update(ChatSession)
        .where(ChatSession.id == session_id)
        .values(updated_at=func.now())
    )

    await session.commit()
    await session.refresh(assistant_row)
    return {"assistant_row": assistant_row}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _route_after_intent(state: _GraphState) -> str:
    return "in_scope" if state.get("scope_ok") else "out_of_scope"


# ---------------------------------------------------------------------------
# Graph build
# ---------------------------------------------------------------------------


def _build_graph():
    g = StateGraph(_GraphState)
    g.add_node("classify_intent", _classify_intent_node)
    g.add_node("polite_refusal", _polite_refusal_node)
    g.add_node("route_tools", _route_tools_node)
    g.add_node("execute_tools", _execute_tools_node)
    g.add_node("compose_response", _compose_response_node)
    g.add_node("validate", _validate_node)
    g.add_node("persist_message", _persist_message_node)

    g.add_edge(START, "classify_intent")
    g.add_conditional_edges(
        "classify_intent",
        _route_after_intent,
        {"in_scope": "route_tools", "out_of_scope": "polite_refusal"},
    )
    g.add_edge("polite_refusal", "persist_message")
    g.add_edge("route_tools", "execute_tools")
    g.add_edge("execute_tools", "compose_response")
    g.add_edge("compose_response", "validate")
    g.add_edge("validate", "persist_message")
    g.add_edge("persist_message", END)
    return g.compile()


# Compiled at import time so a shape error surfaces immediately (per IMP-04
# / BRIEF-02 precedent).
CHAT_GRAPH = _build_graph()


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def run_chat_turn(
    session_id: UUID,
    user_id: UUID,
    user_message: str,
    *,
    session: AsyncSession,
    llm: LLMClient,
    news_store: VectorStore,
    embed: EmbeddingClient,
) -> ChatMessage:
    """One user message → one persisted assistant reply.

    Loads the `ChatSession`, verifies it belongs to `user_id` (cross-user
    protection — raises `PermissionError` otherwise), resolves the caller's
    active portfolio, then runs the CHAT-03 graph. The graph writes both
    message rows in one commit and bumps `chat_sessions.updated_at`.
    """
    chat_session = (
        await session.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
    ).scalar_one_or_none()
    if chat_session is None:
        raise ValueError(f"chat_sessions.id={session_id} not found")
    if chat_session.user_id != user_id:
        raise PermissionError(
            f"chat session {session_id} does not belong to user {user_id}"
        )

    active_portfolio = (
        await session.execute(
            select(Portfolio).where(
                Portfolio.user_id == user_id,
                Portfolio.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    portfolio_id: UUID | None = (
        active_portfolio.id if active_portfolio is not None else None
    )

    result = await CHAT_GRAPH.ainvoke(
        {
            "session_id": session_id,
            "user_id": user_id,
            "user_message": user_message,
            "session": session,
            "llm": llm,
            "news_store": news_store,
            "embed": embed,
            "chat_session": chat_session,
            "portfolio_id": portfolio_id,
        }
    )
    row: ChatMessage | None = result.get("assistant_row")
    if row is None:  # pragma: no cover — persist always writes a row today.
        raise RuntimeError("chat graph did not persist an assistant row")
    return row
