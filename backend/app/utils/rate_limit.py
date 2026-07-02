"""In-process per-model rate limiter for free-tier LLM calls.

Free-tier OpenRouter models are typically capped at 20 RPM per model. This
module keeps one sliding-window bucket per model_id; `acquire(model)` returns
once a slot is free (or raises `RateLimitExceeded` if the wait queue is over
capacity).

Configurable via `Config.LLM_RATE_LIMIT_RPM` (JSON: `{"model_id": rpm, ...}`),
with a `"default"` key used for any model not in the map. Purely in-process:
multi-worker deploys should re-count on each worker, which is intentional at
portfolio scale.
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Deque

from app.utils.config import Config


class RateLimitExceeded(RuntimeError):
    """Raised when the pending queue for a bucket is over capacity."""


class _TokenBucket:
    """Sliding-window bucket: keeps timestamps of the last `rpm` hits."""

    def __init__(self, rpm: int, queue_cap: int = 100):
        self._rpm = max(1, int(rpm))
        self._window = 60.0
        self._hits: Deque[float] = deque()
        self._lock = asyncio.Lock()
        self._queue_cap = queue_cap
        self._pending = 0

    async def acquire(self) -> None:
        while True:
            wait_for: float | None = None
            async with self._lock:
                now = time.monotonic()
                while self._hits and now - self._hits[0] >= self._window:
                    self._hits.popleft()
                if len(self._hits) < self._rpm:
                    self._hits.append(now)
                    return
                if self._pending >= self._queue_cap:
                    raise RateLimitExceeded(
                        f"rate limit queue full (cap={self._queue_cap})"
                    )
                wait_for = max(0.01, self._window - (now - self._hits[0]) + 0.01)
                self._pending += 1
            try:
                await asyncio.sleep(wait_for)
            finally:
                async with self._lock:
                    self._pending -= 1


class RateLimiter:
    """Manages one `_TokenBucket` per model id."""

    def __init__(self, rpm_map: dict[str, int] | None = None, queue_cap: int = 100):
        self._rpm_map = rpm_map if rpm_map is not None else Config.LLM_RATE_LIMIT_RPM
        self._buckets: dict[str, _TokenBucket] = {}
        self._queue_cap = queue_cap

    def _rpm_for(self, model: str) -> int:
        if model in self._rpm_map:
            return int(self._rpm_map[model])
        return int(self._rpm_map.get("default", 20))

    def _bucket(self, model: str) -> _TokenBucket:
        b = self._buckets.get(model)
        if b is None:
            b = self._buckets[model] = _TokenBucket(
                self._rpm_for(model), self._queue_cap
            )
        return b

    async def acquire(self, model: str) -> None:
        await self._bucket(model).acquire()


_default = RateLimiter()


async def acquire(model: str) -> None:
    """Default process-wide entrypoint. Tests can instantiate their own `RateLimiter`."""
    await _default.acquire(model)
