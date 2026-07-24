"""Curated preset scenarios for the scenario simulator (SIM-03).

The frontend shows these as one-click chips on the scenarios page (SIM-04).
Clicking a chip POSTs the `scenario_text` to `/api/scenarios/simulate`; the
SIM-02 graph then produces a full `ScenarioSimulation`.

Presets are curated for demo value — they cover the macro categories a
recruiter or a first-time user might reach for. Each preset is stable across
sessions (identified by its `id`) so a UI can, for example, remember which
preset the user last ran.

To add a preset: append a new `Preset(...)` to `_PRESETS`. Keep the list at
around 10 — this is a chip UI, not a menu.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    """One preset scenario a user can invoke with one click."""

    id: str            # short, stable, kebab-case
    title: str         # short chip label (≤ 40 chars)
    scenario_text: str # full text passed to `simulate_scenario`
    category: str      # loose grouping — "monetary", "geopolitical", …


_PRESETS: tuple[Preset, ...] = (
    Preset(
        id="fed-cuts-50bps",
        title="Fed cuts 50bps at next FOMC",
        scenario_text=(
            "The Federal Reserve cuts the federal funds rate by 50 basis "
            "points at the next FOMC meeting, citing softening labor markets "
            "and easing inflation. Bond yields fall across the curve; equities "
            "rally on the rate relief but growth stocks lead defensives."
        ),
        category="monetary",
    ),
    Preset(
        id="fed-hikes-25bps-surprise",
        title="Fed hikes 25bps unexpectedly",
        scenario_text=(
            "The Fed surprises markets with a 25 basis-point hike at the next "
            "FOMC, citing sticky services inflation. Two-year yields spike; "
            "duration-sensitive assets sell off; the yield curve flattens."
        ),
        category="monetary",
    ),
    Preset(
        id="us-recession-q3",
        title="US recession in Q3",
        scenario_text=(
            "The US economy enters a technical recession in Q3, with two "
            "consecutive quarters of negative GDP growth. Consumer discretionary "
            "spending contracts sharply; unemployment ticks up 80 basis points "
            "over six months; the Fed pivots to rate cuts by year-end."
        ),
        category="macro",
    ),
    Preset(
        id="oil-to-120",
        title="Brent crude spikes to $120",
        scenario_text=(
            "Geopolitical escalation in the Middle East pushes Brent crude "
            "above $120 per barrel and holds it there for three months. Energy "
            "equities rally; airlines and consumer staples face margin pressure; "
            "headline CPI reaccelerates on the pass-through."
        ),
        category="commodity",
    ),
    Preset(
        id="ai-capex-continues",
        title="AI capex cycle continues 12 months",
        scenario_text=(
            "Hyperscaler capex on AI infrastructure grows another 40% year-over-"
            "year over the next twelve months, driven by continued strong "
            "enterprise adoption. Data-center-adjacent semis, power, and cooling "
            "vendors see revenue upside; free cash flow among the hyperscalers "
            "compresses."
        ),
        category="thematic",
    ),
    Preset(
        id="ai-capex-slowdown",
        title="AI capex slows 30% next quarter",
        scenario_text=(
            "Hyperscaler AI-infrastructure capex growth decelerates from +40% "
            "to +10% year-over-year in the coming quarter, as enterprise ROI "
            "concerns take hold. GPU and networking semiconductor revenue "
            "growth halves; hyperscaler free cash flow expands."
        ),
        category="thematic",
    ),
    Preset(
        id="india-rate-cuts-100bps",
        title="RBI cuts rates 100bps",
        scenario_text=(
            "The Reserve Bank of India cuts the policy repo rate by a "
            "cumulative 100 basis points over the next two meetings, citing "
            "moderating inflation and slowing growth. INR weakens vs USD; "
            "Indian rate-sensitive equities (banks, autos, real estate) rally."
        ),
        category="monetary",
    ),
    Preset(
        id="china-stimulus-large",
        title="China rolls out large fiscal stimulus",
        scenario_text=(
            "China's central government announces a fiscal stimulus package "
            "equivalent to ~5% of GDP, targeted at property completion, local-"
            "government debt swaps, and consumer subsidies. Global materials "
            "and industrials rally on the demand impulse; iron ore and copper "
            "prices rise."
        ),
        category="geopolitical",
    ),
    Preset(
        id="global-tariff-escalation",
        title="US tariffs escalate 25% on China imports",
        scenario_text=(
            "The US administration raises tariffs by an additional 25 "
            "percentage points on a broad basket of Chinese imports. Global "
            "supply-chain-exposed multinationals face margin compression; "
            "domestic manufacturers see order flow; USDCNY weakens; equity "
            "volatility rises."
        ),
        category="geopolitical",
    ),
    Preset(
        id="crypto-etf-boom",
        title="Spot crypto ETF flows accelerate",
        scenario_text=(
            "Institutional inflows into US spot crypto ETFs accelerate to "
            "$5B/month, driven by pension fund allocation policy changes. "
            "Bitcoin and Ether prices push to new highs; crypto-exposed "
            "equities (miners, exchanges) outperform; correlation to tech "
            "growth stocks weakens."
        ),
        category="crypto",
    ),
)


def list_presets() -> list[Preset]:
    """Return the curated presets in display order (stable)."""
    return list(_PRESETS)


def get_preset(preset_id: str) -> Preset | None:
    """Look up a preset by its stable `id`. Returns None if not found."""
    for p in _PRESETS:
        if p.id == preset_id:
            return p
    return None
