"""Safe API error responses — never leak stack traces or internals to clients."""
from __future__ import annotations

import logging
from typing import Any

from flask import jsonify

logger = logging.getLogger(__name__)


def api_error(
    message: str,
    *,
    status: int = 500,
    code: str = "internal_error",
    log: Exception | str | None = None,
) -> tuple[Any, int]:
    """Return a generic JSON error and log details server-side."""
    if log is not None:
        if isinstance(log, Exception):
            logger.exception("API error (%s): %s", code, log)
        else:
            logger.error("API error (%s): %s", code, log)
    return jsonify({"success": False, "error": message, "code": code}), status
