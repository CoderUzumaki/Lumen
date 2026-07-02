"""LLM trace routing (BOOT-06 scope: init only, real emission is minimal).

- LangSmith wins if `LANGSMITH_API_KEY` is set (its SDK reads env vars directly).
- Otherwise Langfuse if `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` are set.
- Otherwise no-op.

`current_run_id()` / `set_run_id()` provide a contextvar-based run id so
downstream LLM calls in the same request inherit the parent trace. Full
emission (spans, prompts, outputs) is done by whichever backend's own SDK
gets called by later modules — this module owns the routing decision only.
"""
from __future__ import annotations

import contextvars
import logging

from app.utils.config import Config

log = logging.getLogger(__name__)


_current_run: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "lumen_trace_run", default=None
)


def _langsmith_configured() -> bool:
    return bool(Config.LANGSMITH_API_KEY)


def _langfuse_configured() -> bool:
    return bool(Config.LANGFUSE_PUBLIC_KEY and Config.LANGFUSE_SECRET_KEY)


def active_backend() -> str:
    if _langsmith_configured():
        return "langsmith"
    if _langfuse_configured():
        return "langfuse"
    return "noop"


def init_tracing() -> None:
    """Best-effort init at app startup. Never raises."""
    backend = active_backend()
    if backend == "langsmith":
        log.info("tracing: LangSmith enabled (project=%s)", Config.LANGSMITH_PROJECT)
    elif backend == "langfuse":
        log.info("tracing: Langfuse enabled (host=%s)", Config.LANGFUSE_HOST)
    else:
        log.info("tracing: no backend configured (no-op)")


def current_run_id() -> str | None:
    return _current_run.get()


def set_run_id(run_id: str | None) -> contextvars.Token:
    """Attach `run_id` to the current async context. Reset with `_current_run.reset(token)`."""
    return _current_run.set(run_id)
