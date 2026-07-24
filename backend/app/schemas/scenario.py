"""Pydantic schemas for the scenario simulator (SIM-01/SIM-02).

- `PositionImpact` — one per-ticker impact row inside a `ScenarioSimulation`.
- `ScenarioSimulation` — the structured LLM output the SIM-02 graph produces
  for one (scenario_text, portfolio) pair.

Deviation from PRD principle #1 ("every claim cites a source"): a scenario
is inherently hypothetical, so `citations` may be empty here — the graph
leans on retrieved historical analogs for grounding instead. `ImpactAssessment`
(the news-driven counterpart) still requires ``min_length=1`` on citations
because those claims are anchored in concrete news sources.

The `SIM-01` endpoint (deferred, not yet built) will re-export this same
schema as the wire response type. SIM-02 imports it as the LLM
`response_model=` and returns it directly — no persistence.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.impact import Citation, HistoricalAnalog


class PositionImpact(BaseModel):
    """One per-position row inside a scenario simulation."""

    ticker: str = Field(min_length=1, max_length=20)
    mechanism: str = Field(min_length=20, max_length=800)
    magnitude_low: float | None = None
    magnitude_high: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class ScenarioSimulation(BaseModel):
    """Structured LLM output — one scenario × one portfolio."""

    scenario_text: str = Field(min_length=1, max_length=2000)
    per_position_impact: list[PositionImpact] = Field(default_factory=list)
    portfolio_summary: str = Field(min_length=20, max_length=1500)
    citations: list[Citation] = Field(default_factory=list)
    historical_analogs: list[HistoricalAnalog] = Field(default_factory=list)
    key_assumptions: list[str] = Field(default_factory=list, max_length=10)
    falsifiability: str = Field(min_length=20, max_length=500)
