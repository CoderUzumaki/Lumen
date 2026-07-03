"""Pydantic schemas for the news pipeline (ING-01).

- `NewsItemIn` is the shape ingest adapters produce (before URL hashing / cluster
  assignment). ING-08's normalizer turns these into `news_items` rows.
- `NewsItemRead` is the read shape (adds DB-generated fields).
- `NewsClusterRead` embeds its items — routes in REL-06 use this for the feed.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


NewsSource = Literal["newsapi", "marketaux", "gdelt", "edgar", "rss"]


class NewsItemIn(BaseModel):
    """Adapter output — one item as pulled from a source, before persistence."""

    model_config = ConfigDict(from_attributes=True)

    source: NewsSource
    source_id: str | None = None
    url: HttpUrl
    title: str = Field(min_length=1)
    body: str | None = None
    published_at: datetime
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    # Extensibility slot for source-specific hints (tickers, entities, topics,
    # …). Populated by adapters that produce structured entity data (e.g.
    # Marketaux's `entities[].symbol`); left `{}` by adapters that don't.
    hints: dict[str, Any] = Field(default_factory=dict)


class NewsItemRead(BaseModel):
    """Response shape for a persisted news item."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cluster_id: UUID | None
    source: NewsSource
    source_id: str | None
    url: str
    url_hash: str
    title: str
    body: str | None
    published_at: datetime
    ingested_at: datetime


class NewsClusterRead(BaseModel):
    """Response shape for a deduped event cluster. Embeds its items."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    canonical_title: str
    canonical_summary: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    entity_tickers: list[str]
    entity_topics: list[str]
    authority_score: Decimal
    novelty_score: Decimal
    items: list[NewsItemRead] = Field(default_factory=list)


class IngestRunRead(BaseModel):
    """Response shape for an ingest heartbeat / audit row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: NewsSource
    started_at: datetime
    finished_at: datetime | None
    items_fetched: int | None
    items_new: int | None
    items_deduped: int | None
    error: str | None
