"""Pydantic schemas for the daily briefing (BRIEF-01).

- `BriefingItem` — one bullet in `top_movers` / `watchlist`, tying an impact
  assessment to a concise headline the UI can render.
- `BriefingContent` — the full structured payload persisted to
  `briefings.structured_content`. The BRIEF-02 synthesizer agent produces
  this shape from the day's impact assessments.
- `BriefingRead` — response shape for `GET /api/briefings/...` endpoints
  (added by later modules). Maps 1:1 to `app/db/models/briefing.py::Briefing`.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BriefingItem(BaseModel):
    """One narrative item in `top_movers` or `watchlist`.

    `affected_positions` carries tickers (not UUIDs) — the UI renders them
    directly and the underlying `impact_id` links back to the full assessment.
    """

    impact_id: UUID
    cluster_title: str = Field(min_length=1, max_length=300)
    one_line_summary: str = Field(max_length=200)
    affected_positions: list[str]  # tickers
    mechanism_summary: str = Field(max_length=400)
    confidence: float = Field(ge=0.0, le=1.0)


class BriefingContent(BaseModel):
    """Full structured content of a daily briefing.

    Persisted verbatim into `briefings.structured_content` (JSONB). List caps
    (max_length=5) match the BUILD.md spec for the shipped UI.
    """

    top_movers: list[BriefingItem] = Field(max_length=5)
    watchlist: list[BriefingItem] = Field(max_length=5)
    what_would_change_my_thinking: list[str] = Field(max_length=5)
    generated_summary: str = Field(max_length=800)


class BriefingRead(BaseModel):
    """Response body for a persisted briefings row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    portfolio_id: UUID
    briefing_date: date
    structured_content: BriefingContent
    cited_impact_ids: list[str] = Field(default_factory=list)
    generated_at: datetime
    generation_duration_ms: int | None
    langsmith_run_id: str | None
