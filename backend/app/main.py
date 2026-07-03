from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routes import me as me_routes
from app.routes import portfolios as portfolios_routes
from app.routes import positions as positions_routes
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

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    Config.validate()
    # Best-effort provision of the three canonical Chroma collections (ING-07).
    # Never fatal at boot — if the vector store can't come up, downstream
    # ingestion + retrieval will fail loudly at their call sites instead.
    try:
        from app.db.vectorstore import init_collections
        init_collections()
    except Exception:
        log.exception("vectorstore init_collections failed; continuing without")
    log.info("lumen_startup", extra={"version": app.version})
    yield
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


app.include_router(me_routes.router)
app.include_router(portfolios_routes.router)
app.include_router(positions_routes.router)
