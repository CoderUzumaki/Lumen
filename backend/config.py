"""Application configuration.

All runtime values that change between environments live here. Production
code MUST NOT hardcode database paths, model names, base URLs, ports, or
currency strings — read them from `Config` instead.

`Config.validate()` runs at app startup (see app.py) and raises on missing
required values so the process fails fast rather than producing cryptic
runtime errors.
"""
import logging
import os
import secrets
import warnings
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# Project layout: BACKEND_DIR is the directory this file lives in.
BACKEND_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BACKEND_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)


def _env_path(name: str, default: Path) -> Path:
    """Read a path from env. Relative env values are anchored at BACKEND_DIR."""
    raw = os.getenv(name)
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


_FLASK_ENV = os.getenv("FLASK_ENV", "development")


def _resolve_secret_key(flask_env: str) -> str | None:
    """Resolve SECRET_KEY at import time.

    - If the env var is set, use it.
    - In development, generate an ephemeral per-process key and log a warning
      so dev work isn't blocked. Sessions will not survive a process restart.
    - In any other environment, return None so `Config.validate()` can raise
      with a clear error message instead of silently using a guessable default.
    """
    raw = os.getenv("SECRET_KEY")
    if raw:
        return raw
    if flask_env == "development":
        ephemeral = secrets.token_urlsafe(32)
        # configure_logging() may not have run yet at this point, so emit
        # both a stdlib warning (always visible on stderr) and a logger
        # message (captured once logging is configured).
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
    """Base configuration class. All values are class attributes; read them as
    `Config.OPENROUTER_API_KEY`, never `os.getenv(...)` directly outside this file."""

    # === Flask ===
    FLASK_ENV = _FLASK_ENV
    DEBUG = _FLASK_ENV == "development"
    SECRET_KEY = _resolve_secret_key(_FLASK_ENV)

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 5000))

    # === CORS ===
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    # Comma-separated list of allowed origins for CORS. CFG-04 will tighten this.
    ALLOWED_ORIGINS = [
        o.strip() for o in os.getenv("ALLOWED_ORIGINS", FRONTEND_URL).split(",") if o.strip()
    ]

    # === Storage paths (all absolute) ===
    DATABASE_PATH = _env_path("DATABASE_PATH", INSTANCE_DIR / "lumen.db")

    @staticmethod
    def _resolve_database_uri() -> str:
        """Prefer DATABASE_URL (Postgres on Render); fall back to local SQLite."""
        raw = (os.getenv("DATABASE_URL") or "").strip()
        if raw:
            url = raw
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            try:
                from sqlalchemy.engine import make_url

                make_url(url)
                return url
            except Exception:
                logging.getLogger(__name__).warning(
                    "DATABASE_URL is set but not a valid SQLAlchemy URL; "
                    "falling back to SQLite at %s",
                    Config.DATABASE_PATH,
                )

        # Use forward slashes so Windows paths parse correctly (sqlite:///C:/...)
        path = Config.DATABASE_PATH.as_posix()
        return f"sqlite:///{path}"

    DATABASE_URI = None  # set after class body

    CHROMA_DB_PATH = _env_path("CHROMA_DB_PATH", BACKEND_DIR / "chroma_db")

    # Fixed dev UUID for demo seed data (see docs/AUTH.md)
    DEV_USER_ID = os.getenv(
        "DEV_USER_ID", "00000000-0000-0000-0000-000000000123"
    )

    # Chroma/RAG — disable on Render unless a persistent disk is mounted
    ENABLE_CHROMA = os.getenv("ENABLE_CHROMA", "true").lower() in (
        "1",
        "true",
        "yes",
    )

    # === OpenRouter / LLM ===
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_CHAT_URL = f"{OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"

    # Vision-capable model used for OCR / invoice extraction (`utils/openrouter.py`).
    LLM_VISION_MODEL = os.getenv(
        "LLM_VISION_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free"
    )
    # Text model used for chat synthesis, SQL generation, classification,
    # anomaly explanation, forecasting reasoning.
    LLM_TEXT_MODEL = os.getenv("LLM_TEXT_MODEL") or "openrouter/free"

    @classmethod
    def get_llm_text_model(cls) -> str:
        """Resolve the text model from the live environment (not import-time cache)."""
        return os.getenv("LLM_TEXT_MODEL") or cls.LLM_TEXT_MODEL or "openrouter/free"
    # Embedding model used by the RAG store.
    LLM_EMBEDDING_MODEL = os.getenv("LLM_EMBEDDING_MODEL", "openai/text-embedding-3-small")

    # Legacy alias: some older modules still read `OPENROUTER_MODEL` from the
    # environment. Keep the alias so they get the text model by default.
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", LLM_TEXT_MODEL)

    # === Upload limits ===
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
    MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

    # === Localization ===
    DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "INR")

    # === Supabase Auth ===
    # SUPABASE_URL is the project URL (e.g. https://abcdef.supabase.co). Required
    # once @require_auth is applied to routes (AUTH-03). Until then the decorator
    # raises a clear error if any protected route is hit without it.
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    # The expected `aud` claim in incoming JWTs. Supabase uses "authenticated"
    # for end-user sessions by default; surface as config so test fixtures and
    # alternative tenants can override.
    SUPABASE_JWT_AUD = os.getenv("SUPABASE_JWT_AUD", "authenticated")
    # Legacy: the anon/publishable key. Currently unused by the backend (the
    # frontend uses it, via NEXT_PUBLIC_SUPABASE_ANON_KEY). Kept here so a future
    # backend feature that needs to call Supabase REST as the anonymous role
    # doesn't need a config change.
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    @classmethod
    def validate(cls) -> None:
        """Raise ValueError on missing required configuration.

        Called once at app startup. Add to the `required` list when a feature
        becomes load-bearing. Optional dependencies (Supabase, email polling)
        should validate themselves where they're used, not here.

        SECRET_KEY is enforced here too: in dev mode `_resolve_secret_key`
        supplies an ephemeral value so it's never missing; in any other
        environment a missing `SECRET_KEY` env var leaves it `None` and we
        refuse to start.
        """
        required = {
            "OPENROUTER_API_KEY": cls.OPENROUTER_API_KEY,
            "SECRET_KEY": cls.SECRET_KEY,
            "SUPABASE_URL": cls.SUPABASE_URL,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Set them in your .env file or shell environment before starting the app."
            )


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

# Resolve DATABASE_URI after class definition (needs DATABASE_PATH).
Config.DATABASE_URI = Config._resolve_database_uri()
