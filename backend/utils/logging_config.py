"""Centralized logging configuration.

Call `configure_logging()` once at process start (done in app.py).
Every module then uses `logger = logging.getLogger(__name__)`.

Environment:
    LOG_LEVEL   DEBUG | INFO | WARNING | ERROR | CRITICAL  (default INFO)
    LOG_FORMAT  'plain' | 'json'                            (default 'plain')
"""

import logging
import os
import sys


_CONFIGURED = False


def configure_logging() -> None:
    """Configure the root logger. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # On Windows, stdout redirected to a file or pipe uses cp1252, which can't
    # encode the emoji some log messages contain; the handler then prints a
    # "--- Logging error ---" traceback for every such line. Replace
    # unencodable characters instead of failing.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(errors="replace")
        except (ValueError, OSError):
            pass

    handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    # Replace any handlers Flask / Gunicorn may have attached
    root.handlers = [handler]
    root.setLevel(level)

    # Quiet down noisy third-party loggers unless the user explicitly raised the level.
    if level > logging.DEBUG:
        for noisy in ("werkzeug", "urllib3", "chromadb.telemetry"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    # chromadb 0.5 calls posthog.capture() with a signature posthog>=6 rejects,
    # logging an ERROR on every client start even though telemetry is disabled
    # (see ai/rag_system.py). Nothing is sent either way, so drop the noise.
    logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

    _CONFIGURED = True


def mask_secret(value: str | None, keep: int = 4) -> str:
    """Render a secret safely for logs as `****` plus its last `keep` chars.

    Fixed-width so the log doesn't reveal the secret's length.
    """
    if not value:
        return "<unset>"
    if len(value) <= keep * 2:
        return "****"
    return f"****{value[-keep:]}"
