"use client";

/**
 * Typed API client + TanStack Query hooks for /api/scenarios/*.
 *
 * The SSE side of the endpoint (`POST /api/scenarios/simulate`) is consumed via
 * `useSse` in `@/hooks/use-sse` — this file covers only the JSON endpoint
 * (`GET /api/scenarios/presets`) plus the shared type definitions.
 *
 * Deviation from PRD principle #1: `ScenarioSimulation.citations` may be empty
 * because a hypothetical scenario doesn't have concrete news sources to anchor;
 * the graph leans on `historical_analogs` for grounding instead. UI copy in
 * SIM-04 reflects this — see `simulation-view.tsx`.
 */
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import type { Citation, HistoricalAnalog } from "@/lib/api/impact";

// ---------------------------------------------------------------------------
// Types — mirror `backend/app/schemas/scenario.py` +
// `backend/app/agents/scenario/presets.py`. Floats here are NOT Decimal
// strings — the scenario schema uses `float` fields, unlike ImpactAssessment.
// ---------------------------------------------------------------------------

export type ScenarioPreset = {
	id: string;
	title: string;
	scenario_text: string;
	category: string;
};

export type PositionImpact = {
	ticker: string;
	mechanism: string;
	magnitude_low: number | null; // fractions, 0.03 = 3%
	magnitude_high: number | null;
	confidence: number; // 0..1 float
};

export type ScenarioSimulation = {
	scenario_text: string;
	per_position_impact: PositionImpact[];
	portfolio_summary: string;
	citations: Citation[];
	historical_analogs: HistoricalAnalog[];
	key_assumptions: string[];
	falsifiability: string;
};

export type ScenarioSimulateInput = {
	scenario_text: string;
	portfolio_id?: string;
};

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const scenarioKeys = {
	all: ["scenarios"] as const,
	presets: () => [...scenarioKeys.all, "presets"] as const,
};

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

/**
 * Curated preset scenarios (SIM-03). One click loads the preset's
 * `scenario_text` into the composer; the user still submits explicitly.
 */
export function useScenarioPresets(options?: { enabled?: boolean }) {
	return useQuery<ScenarioPreset[]>({
		queryKey: scenarioKeys.presets(),
		queryFn: () => apiFetch<ScenarioPreset[]>("/api/scenarios/presets"),
		// Presets are static per deploy — cache them aggressively.
		staleTime: 5 * 60 * 1000,
		enabled: options?.enabled,
	});
}

// ---------------------------------------------------------------------------
// SSE frame types — for `POST /api/scenarios/simulate`
// ---------------------------------------------------------------------------

export type ScenarioNodeStarted = {
	event: "node_started";
	data: { node: string };
};
export type ScenarioNodeCompleted = {
	event: "node_completed";
	data: { node: string; duration_ms: number };
};
export type ScenarioResult = {
	event: "result";
	data: ScenarioSimulation;
};
export type ScenarioStreamComplete = {
	event: "complete";
	data: { scenario_text: string };
};
export type ScenarioStreamError = {
	event: "error";
	data: { message: string };
};

export type ScenarioSseEvent =
	| ScenarioNodeStarted
	| ScenarioNodeCompleted
	| ScenarioResult
	| ScenarioStreamComplete
	| ScenarioStreamError
	| { event: string; data: unknown };
