from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.db.base import get_db_session
from app.pipelines.orchestrator import _to_health_payload, latest_per_source
from app.routes import impact as impact_routes
from app.routes import me as me_routes
from app.routes import news as news_routes
from app.routes import portfolios as portfolios_routes
from app.routes import positions as positions_routes
from app.routes import themes as themes_routes
from app.utils.config import Config
from app.utils.logging_config import configure_logging

log = logging.getLogger("lumen")


# --- Envelope helpers --------------------------------------------------------
# BUILD.md §Global conventions → Error envelope:
#   { "data": <T> | null, "error": { "code", "message", "details"? } | null }
# 2xx → data populated, error null. 4xx/5xx → data null, error populated.

def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None}


def _err(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"data": None, "error": body}


_HTTP_CODE_MAP: dict[int, str] = {
    400: "validation_error",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
}


# --- Lifespan ----------------------------------------------------------------
# BOOT-06 will wire LangSmith / Langfuse tracing here.

_scheduler: Any | None = None


def _build_default_orchestrator():
    """Construct the process-global IngestOrchestrator + start APScheduler.

    Kept behind a try/except at the call site — a broken schedule shouldn't
    kill the API. Returns the started scheduler (or None if disabled).

    Each scheduled tick runs one ingest pass and then fans out relevance
    scoring across every active portfolio (REL-05).
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    from app.db.base import get_session_factory
    from app.db.vectorstore import VectorStore
    from app.pipelines.briefing_scheduler import run_briefing_scheduler
    from app.pipelines.orchestrator import IngestOrchestrator, default_source_factory
    from app.pipelines.relevance_fanout import run_fanout
    from app.utils.embeddings import EmbeddingClient
    from app.utils.llm import LLMClient

    factory = get_session_factory()
    embed = EmbeddingClient()
    news_store = VectorStore("news_items")
    themes_store = VectorStore("themes")
    llm = LLMClient()
    orchestrator = IngestOrchestrator(
        session_factory=factory,
        embed=embed,
        store=news_store,
        source_factory=default_source_factory,
    )

    async def _ingest_and_fanout() -> None:
        cycle_started = datetime.now(timezone.utc)
        try:
            await orchestrator.run()
        except Exception:
            log.exception("scheduler: ingest run failed")
            return
        try:
            await run_fanout(
                session_factory=factory,
                news_store=news_store,
                themes_store=themes_store,
                embed=embed,
                llm=llm,
                since=cycle_started,
            )
        except Exception:
            log.exception("scheduler: fanout run failed")

    async def _briefing_tick() -> None:
        try:
            await run_briefing_scheduler(session_factory=factory, llm=llm)
        except Exception:
            log.exception("scheduler: briefing tick failed")

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _ingest_and_fanout,
        trigger=IntervalTrigger(minutes=Config.INGEST_INTERVAL_MINUTES),
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=30),
        id="lumen-ingest",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    # BRIEF-03: check every 15 min whether any user's local briefing hour
    # matches now. Idempotent — synthesize_briefing_for_user rejects duplicates.
    scheduler.add_job(
        _briefing_tick,
        trigger=IntervalTrigger(minutes=15),
        next_run_time=datetime.now(timezone.utc) + timedelta(minutes=1),
        id="lumen-briefing",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("Scheduler started; first ingest in 30s, first briefing tick in 60s")
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _scheduler
    configure_logging()
    Config.validate()
    # Best-effort provision of the three canonical Chroma collections (ING-07).
    try:
        from app.db.vectorstore import init_collections
        init_collections()
    except Exception:
        log.exception("vectorstore init_collections failed; continuing without")
    # Best-effort start of the ingest scheduler (ING-10).
    try:
        _scheduler = _build_default_orchestrator()
    except Exception:
        log.exception("ingest scheduler failed to start; API will run without it")
        _scheduler = None
    log.info("lumen_startup", extra={"version": app.version})
    yield
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            log.exception("ingest scheduler shutdown failed")
    log.info("lumen_shutdown")


# --- App ---------------------------------------------------------------------

app = FastAPI(
    title="Lumen Intelligence Agent",
    version="0.1.0",
    lifespan=lifespan,
)


def _allowed_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
    if not raw:
        return ["http://localhost:3000"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.ALLOWED_ORIGINS or _allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# --- Exception handlers ------------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _HTTP_CODE_MAP.get(exc.status_code, "internal_error")
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(status_code=exc.status_code, content=_err(code, detail))


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # DATA-03's acceptance requires ticker validation failures to return 400
    # (with the `validation_error` code) — deviating from FastAPI's default
    # 422 to match BUILD.md's stable-code contract.
    return JSONResponse(
        status_code=400,
        content=_err("validation_error", "Request validation failed", details=exc.errors()),
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception", extra={"path": str(request.url.path)})
    return JSONResponse(
        status_code=500,
        content=_err("internal_error", "Internal server error"),
    )


# --- Routes ------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, Any]:
    return _ok({"status": "ok", "commit": os.environ.get("GIT_SHA", "dev")})


@app.get("/health/ingest")
async def health_ingest(
    db=Depends(get_db_session),
) -> dict[str, Any]:
    rows = await latest_per_source(db)
    return _ok({"sources": _to_health_payload(rows)})


app.include_router(me_routes.router)
app.include_router(portfolios_routes.router)
app.include_router(positions_routes.router)
app.include_router(themes_routes.router)
app.include_router(news_routes.router)
app.include_router(impact_routes.router)
