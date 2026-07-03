"""Shared interface for news source adapters (ING-02..ING-06).

Every source implements `fetch(since)` and returns a list of `NewsItemIn`.
The orchestrator (ING-10) fans out across all enabled sources; each adapter
is responsible for its own rate limiting, retries, and error handling. Never
raise — return an empty list and log — so one flaky source doesn't take down
the whole pipeline.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.schemas.news import NewsItemIn


class BaseSource(ABC):
    """Abstract base for a news adapter."""

    #: Stable identifier stored in `news_items.source`. Must match one of the
    #: 5 CHECK-constraint values on the table.
    source_name: str

    @abstractmethod
    async def fetch(self, since: datetime) -> list[NewsItemIn]:
        """Return items published at or after `since`.

        Contract:
        - Never raise on transient failures — log and return `[]`.
        - Never raise on missing credentials — log and return `[]`.
        - Retry on 429 / 5xx internally (with backoff).
        """
