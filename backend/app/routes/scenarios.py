"""Scenario endpoints (SIM-01) + preset chip listing (SIM-03).

Two endpoints, both authed via `require_auth`:

- `POST /api/scenarios/simulate` — SSE stream of scenario analysis. Body:
  `ScenarioSimulateRequest` (`scenario_text`, optional `portfolio_id` — defaults
  to the caller's active portfolio). Emits `node_started`, `node_completed`,
  `result` (the serialized `ScenarioSimulation`), `complete`, or `error`.

- `GET /api/scenarios/presets` — the curated preset chips from SIM-03. Returns
  a list of `{id, title, scenario_text, category}` records.

Cross-user isolation: if the caller passes a `portfolio_id` that isn't theirs,
the endpoint returns 404 (same shape as REL-06 / IMP-05 — never leak existence).
If `portfolio_id` is omitted, we use `SELECT Portfolio WHERE user_id=caller AND
is_active=TRUE`; 404 if none.

Deviation from BUILD.md (mirrors BRIEF-04 + CHAT-04): the SSE stream emits a
single `simulator` pseudo-node envelope around the whole `simulate_scenario`
invocation. Per-node streaming waits on a LangGraph `astream_events` refactor
in SIM-02.

`get_scenario_runner` is an injectable FastAPI dependency so tests can
substitute a stub without touching the real graph / Chroma / LLM.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator, Awaitable, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.scenario.graph import simulate_scenario as _default_simulate
from app.agents.scenario.presets import Preset, list_presets
from app.db.base import get_db_session, get_session_factory
from app.db.models.portfolio import Portfolio
from app.db.vectorstore import VectorStore
from app.schemas.scenario import ScenarioSimulateRequest, ScenarioSimulation
from app.utils.auth import UserContext, require_auth
from app.utils.embeddings import EmbeddingClient
from app.utils.llm import LLMClient

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


# Injectable simulator runner. Signature intentionally minimal — the endpoint
# passes user_id / portfolio_id / scenario_text; the runner constructs its own
# session, analogs_store, embed, and llm (the request-scoped session dies
# before the SSE finishes, same reason CHAT-04's runner is self-contained).
ScenarioRunnerFn = Callable[[UUID, UUID, str], Awaitable[ScenarioSimulation | None]]


async def _default_runner(
    user_id: UUID, portfolio_id: UUID, scenario_text: str
) -> ScenarioSimulation | None:
    session_factory = get_session_factory()
    analogs_store = VectorStore("historical_analogs")
    embed = EmbeddingClient()
    llm = LLMClient()
    async with session_factory() as session:
        return await _default_simulate(
            user_id,
            portfolio_id,
            scenario_text,
            session=session,
            analogs_store=analogs_store,
            embed=embed,
            llm=llm,
        )


def get_scenario_runner() -> ScenarioRunnerFn:
    """FastAPI dependency — swap via `app.dependency_overrides` in tests."""
    return _default_runner


async def _active_portfolio(user_id: UUID, db: AsyncSession) -> Portfolio | None:
    q = select(Portfolio).where(
        Portfolio.user_id == user_id, Portfolio.is_active.is_(True)
    )
    return (await db.execute(q)).scalar_one_or_none()


async def _owned_portfolio(
    user_id: UUID, portfolio_id: UUID, db: AsyncSession
) -> Portfolio | None:
    q = select(Portfolio).where(
        Portfolio.id == portfolio_id, Portfolio.user_id == user_id
    )
    return (await db.execute(q)).scalar_one_or_none()


def _sse_event(event: str, data: Any) -> bytes:
    """One SSE frame: `event: <name>\\ndata: <json>\\n\\n` UTF-8 encoded."""
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


async def _simulate_sse_generator(
    user_id: UUID, portfolio_id: UUID, scenario_text: str, runner: ScenarioRunnerFn
) -> AsyncIterator[bytes]:
    """Yield SSE frames for one scenario simulation."""
    yield _sse_event("node_started", {"node": "simulator"})

    started = time.monotonic()
    result: ScenarioSimulation | None
    try:
        result = await runner(user_id, portfolio_id, scenario_text)
    except Exception as exc:  # noqa: BLE001 — surface to the client, don't crash
        log.exception(
            "scenarios SSE simulation failed user=%s portfolio=%s",
            user_id,
            portfolio_id,
        )
        yield _sse_event("error", {"message": str(exc) or "simulation failed"})
        return

    duration_ms = int((time.monotonic() - started) * 1000)
    yield _sse_event(
        "node_completed",
        {"node": "simulator", "duration_ms": duration_ms},
    )

    if result is None:
        yield _sse_event(
            "error",
            {"message": "simulation returned no result (LLM failure or guardrail violation)"},
        )
        return

    yield _sse_event("result", result.model_dump(mode="json"))
    yield _sse_event("complete", {"scenario_text": scenario_text})


# ---------------------------------------------------------------------------
# POST /api/scenarios/simulate
# ---------------------------------------------------------------------------


@router.post("/simulate", name="simulate_scenario")
async def simulate_endpoint(
    body: ScenarioSimulateRequest,
    user: UserContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db_session),
    runner: ScenarioRunnerFn = Depends(get_scenario_runner),
) -> StreamingResponse:
    if body.portfolio_id is not None:
        portfolio = await _owned_portfolio(user.user_id, body.portfolio_id, db)
    else:
        portfolio = await _active_portfolio(user.user_id, db)

    if portfolio is None:
        # 404 for both "no active portfolio" and "portfolio_id not caller's" —
        # matches REL-06 / IMP-05 cross-user existence-hiding.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no active portfolio",
        )

    return StreamingResponse(
        _simulate_sse_generator(
            user.user_id, portfolio.id, body.scenario_text, runner
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx: don't buffer SSE
        },
    )


# ---------------------------------------------------------------------------
# GET /api/scenarios/presets
# ---------------------------------------------------------------------------


@router.get("/presets", name="list_scenario_presets")
async def presets_endpoint(
    _user: UserContext = Depends(require_auth),
) -> list[dict[str, str]]:
    """The curated preset chip list from SIM-03."""
    presets: list[Preset] = list_presets()
    return [
        {
            "id": p.id,
            "title": p.title,
            "scenario_text": p.scenario_text,
            "category": p.category,
        }
        for p in presets
    ]
