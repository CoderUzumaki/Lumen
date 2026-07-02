"""Centralized logging configuration.

Call `configure_logging()` once at process start (from `app.main` lifespan).
Every module then uses `logger = logging.getLogger(__name__)`.

Environment:
    LOG_LEVEL   DEBUG | INFO | WARNING | ERROR | CRITICAL  (default INFO)

BUILD.md §Structured logging targets `structlog` with JSON output. A later
observability module will migrate; BOOT-03 ports the existing stdlib config
verbatim per its Action item 4.
"""
from __future__ import annotations

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

    handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Quiet down noisy third-party loggers unless the user explicitly raised the level.
    if level > logging.DEBUG:
        for noisy in ("urllib3", "chromadb.telemetry", "httpx"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def mask_secret(value: str | None, keep: int = 4) -> str:
    """Render a secret safely for logs: keep last `keep` chars, mask the rest."""
    if not value:
        return "<unset>"
    if len(value) <= keep:
        return "*" * len(value)
    return f"{'*' * (len(value) - keep)}{value[-keep:]}"
