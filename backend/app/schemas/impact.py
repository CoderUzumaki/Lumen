"""Pydantic schemas for the impact analyst (IMP-01).

- `Citation` — one source citation embedded in `ImpactAssessment.citations`.
- `HistoricalAnalog` — one retrieved historical analog embedded in
  `ImpactAssessment.historical_analogs`.
- `ImpactAssessment` — the structured LLM output shape. The IMP-04 agent
  requests this via `response_model=` and the graph persists it to the
  `impact_assessments` table via the ORM `ImpactAssessment` in
  `app/db/models/impact.py` (same name, different module — the ORM class is
  the row, this Pydantic class is the wire payload).
- `ImpactRead` — response shape for `GET /api/news/clusters/{id}` and
  `GET /api/impact/...` endpoints (added by later modules).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Citation(BaseModel):
    """One source citation supporting a claim in the mechanism."""

    source: str = Field(min_length=1, max_length=64)
    url: HttpUrl
    title: str = Field(min_length=1, max_length=500)
    quote: str = Field(max_length=300)


class HistoricalAnalog(BaseModel):
    """One retrieved historical event used as an analog."""

    event_description: str = Field(min_length=1, max_length=500)
    when: date
    outcome_description: str = Field(min_length=1, max_length=500)
    similarity_score: float = Field(ge=0.0, le=1.0)


class ImpactAssessment(BaseModel):
    """Structured LLM output — impact analyst verdict for one (event, portfolio).

    Persisted to the `impact_assessments` table by the IMP-04 agent. Fields
    map 1:1 to the ORM `ImpactAssessment` in `app/db/models/impact.py`
    (identifier/audit columns — `id`, `cluster_id`, `user_id`, `portfolio_id`,
    `raw_llm_output`, `guardrail_violations`, `langsmith_run_id`, `created_at`
    — are set by the agent, not the LLM).
    """

    mechanism: str = Field(min_length=50, max_length=1500)
    magnitude_low: float | None = None
    magnitude_high: float | None = None
    timeframe_days: int | None = Field(default=None, ge=1, le=365)
    confidence: float = Field(ge=0.0, le=1.0)
    falsifiability: str = Field(min_length=20, max_length=500)
    citations: list[Citation] = Field(min_length=1)
    historical_analogs: list[HistoricalAnalog] = Field(default_factory=list)
    affected_positions: list[UUID] = Field(min_length=1)


class ImpactRead(BaseModel):
    """Response body for a persisted impact-assessment row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cluster_id: UUID
    user_id: UUID
    portfolio_id: UUID
    mechanism: str
    magnitude_low: Decimal | None
    magnitude_high: Decimal | None
    timeframe_days: int | None
    confidence: Decimal
    falsifiability: str
    citations: list[Citation]
    historical_analogs: list[HistoricalAnalog] = Field(default_factory=list)
    affected_positions: list[str] = Field(default_factory=list)
    langsmith_run_id: str | None = None
    created_at: datetime
