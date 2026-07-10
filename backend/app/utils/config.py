"""Application configuration.

All runtime values that change between environments live here. Production
code MUST NOT hardcode database URLs, model names, base URLs, ports, or
threshold constants — read them from `Config` instead.

`Config.validate()` runs at app startup (see `app.main`) and raises on
missing required values so the process fails fast rather than producing
cryptic runtime errors.

The authoritative env-var list lives in `BUILD.md` under
"Environment variables — authoritative list". This module MUST stay in
sync with that section; BOOT-07 mirrors the list into `.env.example`.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import warnings
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _env_str(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise ValueError(f"env var {name!r} must be an integer, got {raw!r}") from e


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as e:
        raise ValueError(f"env var {name!r} must be a float, got {raw!r}") from e


def _env_json(name: str, default: dict) -> dict:
    raw = os.getenv(name)
    if not raw:
        return dict(default)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"env var {name!r} must be valid JSON, got {raw!r}") from e
    if not isinstance(parsed, dict):
        raise ValueError(f"env var {name!r} must be a JSON object, got {type(parsed).__name__}")
    return parsed


_FLASK_ENV = os.getenv("FLASK_ENV", "development")


def _resolve_secret_key(flask_env: str) -> str | None:
    """Resolve SECRET_KEY at import time.

    - If the env var is set, use it.
    - In development, generate an ephemeral per-process key and log a warning
      so dev work isn't blocked. Sessions will not survive a process restart.
    - In any other environment, return None so `Config.validate()` raises with
      a clear error instead of silently using a guessable default.
    """
    raw = os.getenv("SECRET_KEY")
    if raw:
        return raw
    if flask_env == "development":
        ephemeral = secrets.token_urlsafe(32)
        msg = (
            "SECRET_KEY is not set; generated an ephemeral key for this dev "
            "process. Sessions will not survive a restart. Set SECRET_KEY in "
            ".env to silence this warning."
        )
        warnings.warn(msg, stacklevel=2)
        logging.getLogger(__name__).warning(msg)
        return ephemeral
    return None


class Config:
    """Base configuration. Read every runtime value via `Config.FOO`, never
    `os.getenv(...)` outside this module."""

    # --- Core ---
    FLASK_ENV = _FLASK_ENV
    DEBUG = _FLASK_ENV == "development"
    SECRET_KEY = _resolve_secret_key(_FLASK_ENV)
    ALLOWED_ORIGINS: list[str] = _env_list("ALLOWED_ORIGINS", ["http://localhost:3000"])
    DATABASE_URL: str = _env_str(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/lumen",
    ) or ""
    LOG_LEVEL: str = _env_str("LOG_LEVEL", "INFO") or "INFO"

    # --- Supabase auth ---
    SUPABASE_URL: str | None = _env_str("SUPABASE_URL")
    SUPABASE_JWT_AUD: str = _env_str("SUPABASE_JWT_AUD", "authenticated") or "authenticated"

    # --- LLM (OpenRouter, free tier) ---
    OPENROUTER_API_KEY: str | None = _env_str("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = _env_str(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    ) or "https://openrouter.ai/api/v1"
    LLM_TEXT_MODEL_FAST: str = _env_str(
        "LLM_TEXT_MODEL_FAST", "meta-llama/llama-3.3-70b-instruct:free"
    ) or "meta-llama/llama-3.3-70b-instruct:free"
    LLM_TEXT_MODEL_THOROUGH: str = _env_str(
        "LLM_TEXT_MODEL_THOROUGH", "deepseek/deepseek-chat-v3.1:free"
    ) or "deepseek/deepseek-chat-v3.1:free"
    LLM_RATE_LIMIT_RPM: dict = _env_json("LLM_RATE_LIMIT_RPM", {"default": 20})
    LLM_DAILY_BUDGET_USD: float = _env_float("LLM_DAILY_BUDGET_USD", 0.0)

    # --- Embeddings (local, free) ---
    EMBEDDING_MODEL: str = _env_str(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    ) or "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = _env_str("EMBEDDING_DEVICE", "cpu") or "cpu"

    # --- Clustering / relevance ---
    # Per-source authority weight in [0, 1]. Feeds ING-09's cluster.authority_score
    # (max over member sources). Higher = more trusted. Override via env with a
    # full JSON object.
    SOURCE_AUTHORITY: dict = _env_json(
        "SOURCE_AUTHORITY",
        {
            "newsapi": 0.60,
            "marketaux": 0.60,
            "gdelt": 0.50,
            "edgar": 0.95,
            "rss": 0.70,
        },
    )

    # --- News sources ---
    NEWSAPI_KEY: str | None = _env_str("NEWSAPI_KEY")
    MARKETAUX_KEY: str | None = _env_str("MARKETAUX_KEY")
    GDELT_ENABLED: bool = _env_bool("GDELT_ENABLED", True)
    EDGAR_USER_AGENT: str = _env_str(
        "EDGAR_USER_AGENT", "Lumen contact@example.com"
    ) or "Lumen contact@example.com"
    RSS_FEEDS: list[str] = _env_list("RSS_FEEDS", [])

    # --- Market data ---
    YFINANCE_CACHE_PATH: str = _env_str("YFINANCE_CACHE_PATH", "/app/price_cache") or "/app/price_cache"

    # --- Vector store ---
    CHROMA_PATH: str = _env_str("CHROMA_PATH", "/app/chroma_data") or "/app/chroma_data"

    # --- Observability (pick ONE; BOOT-06 wires whichever is configured) ---
    LANGSMITH_API_KEY: str | None = _env_str("LANGSMITH_API_KEY")
    LANGSMITH_PROJECT: str = _env_str("LANGSMITH_PROJECT", "lumen-dev") or "lumen-dev"
    LANGSMITH_TRACING: bool = _env_bool("LANGSMITH_TRACING", False)
    LANGFUSE_PUBLIC_KEY: str | None = _env_str("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY: str | None = _env_str("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST: str = _env_str("LANGFUSE_HOST", "https://cloud.langfuse.com") or "https://cloud.langfuse.com"

    # --- Scheduler / pipeline thresholds ---
    INGEST_INTERVAL_MINUTES: int = _env_int("INGEST_INTERVAL_MINUTES", 15)
    CLUSTER_SIMILARITY_THRESHOLD: float = _env_float("CLUSTER_SIMILARITY_THRESHOLD", 0.87)
    PREFILTER_THRESHOLD: float = _env_float("PREFILTER_THRESHOLD", 0.35)

    @classmethod
    def validate(cls) -> None:
        """Raise `ValueError` when any required env var is missing.

        Required set is deliberately small: only the values the app cannot
        boot without in any environment. Optional integrations (news APIs,
        observability backends) validate themselves at their point of use.
        SECRET_KEY is enforced here — in dev `_resolve_secret_key` supplies an
        ephemeral value, so it's only missing when someone explicitly runs
        outside dev without setting it.
        """
        required = {
            "SECRET_KEY": cls.SECRET_KEY,
            "OPENROUTER_API_KEY": cls.OPENROUTER_API_KEY,
            "SUPABASE_URL": cls.SUPABASE_URL,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Set them in your .env file or shell environment before starting the app."
            )
