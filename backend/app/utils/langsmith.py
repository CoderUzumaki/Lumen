"""LangSmith project naming, run tagging, and public-share helpers (EVAL-02).

BOOT-06 already wired the routing decision (`app.utils.tracing.init_tracing`)
and `LLMClient.complete` inherits LangSmith automatically via env vars
(`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`) — the SDK
picks those up on its own. This module layers on:

1. `project_name(env)` — the `lumen-{env}` convention from BUILD.md EVAL-02.
2. `is_tracing_enabled()` — fast-path check callers can use before assembling
   metadata, so no work is done when tracing is off.
3. `run_metadata(...)` — a `{"tags": [...], "metadata": {...}}` dict LangGraph
   graphs can spread into their `ainvoke(state, config=...)` call. Standard
   keys: `agent_name`, `env:<env>`, short `git_sha`. Metadata carries
   `user_id`, `agent_name`, `git_sha`, and any caller-supplied extras.
4. `mark_public(run_id)` — best-effort public-share helper for briefing
   traces. Returns the public URL or `None` on any failure (missing SDK,
   tracing disabled, network error). Never raises.

Env vars this module honors (set via env, not Config, because the LangSmith
SDK reads them directly):

- `LANGSMITH_TRACING` — enable tracing (truthy string).
- `LANGSMITH_API_KEY` — SDK auth.
- `LANGSMITH_PROJECT` — default project name.
- `GIT_SHA` — populates `run_metadata` when the caller doesn't supply one.
- `FLASK_ENV` (via `Config.FLASK_ENV`) — feeds `project_name`.
"""
from __future__ import annotations

import logging
import os
from typing import Any
from uuid import UUID

from app.utils.config import Config

log = logging.getLogger(__name__)


_TRUTHY = frozenset({"true", "1", "yes", "on"})


def _short_sha(sha: str, n: int = 7) -> str:
    return sha[:n] if sha else "dev"


def project_name(env: str | None = None) -> str:
    """Return `lumen-{env}` — the LangSmith project name for this environment.

    - `env` overrides the FLASK_ENV lookup when supplied.
    - `Config.FLASK_ENV`'s `development` / `staging` / `production` map to
      `dev` / `staging` / `prod`. Anything else falls back to `dev`.
    """
    raw = env if env is not None else Config.FLASK_ENV
    mapping = {
        "development": "dev",
        "dev": "dev",
        "staging": "staging",
        "production": "prod",
        "prod": "prod",
    }
    short = mapping.get((raw or "").lower(), "dev")
    return f"lumen-{short}"


def is_tracing_enabled() -> bool:
    """True iff LANGSMITH_TRACING is truthy AND LANGSMITH_API_KEY is set.

    Reads from `os.environ` (not `Config`) because the LangSmith SDK also
    reads env directly — callers changing config at runtime need env, not
    a captured attribute. Both must be present; missing either → False.
    """
    tracing = os.environ.get("LANGSMITH_TRACING", "").strip().lower()
    if tracing not in _TRUTHY:
        return False
    return bool(os.environ.get("LANGSMITH_API_KEY", "").strip())


def run_metadata(
    *,
    agent_name: str,
    user_id: UUID | None = None,
    git_sha: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble `{"tags": [...], "metadata": {...}}` for a LangGraph run.

    Callers spread this into `graph.ainvoke(state, config=run_metadata(...))`.
    Tags are short strings LangSmith uses for filtering; metadata is the
    full context (user_id serialized as str for JSON safety).
    """
    sha = git_sha or os.environ.get("GIT_SHA", "dev")
    env_short = project_name().removeprefix("lumen-")

    tags: list[str] = [agent_name, f"env:{env_short}", _short_sha(sha)]

    metadata: dict[str, Any] = {
        "agent_name": agent_name,
        "git_sha": sha,
    }
    if user_id is not None:
        metadata["user_id"] = str(user_id)
    if extra:
        # Never let extras clobber the standard keys.
        for k, v in extra.items():
            if k in metadata:
                log.warning(
                    "run_metadata: extra key %r collides with reserved key; dropping",
                    k,
                )
                continue
            metadata[k] = v

    return {"tags": tags, "metadata": metadata}


def mark_public(run_id: str) -> str | None:
    """Best-effort: mark a LangSmith run as publicly shareable; return URL or None.

    Fails silently in every failure mode:
    - SDK not installed → None.
    - Tracing not enabled → None (nothing to share).
    - Client construction / share_run RPC raises → None + warning log.
    """
    if not is_tracing_enabled():
        return None

    try:
        from langsmith import Client
    except ImportError:
        log.debug("mark_public: langsmith SDK not installed; skipping share")
        return None

    try:
        client = Client()
        url = client.share_run(run_id)
        return str(url) if url else None
    except Exception as exc:  # noqa: BLE001 — best-effort by contract
        log.warning("mark_public: share_run failed for run=%s: %s", run_id, exc)
        return None
