"use client";

/**
 * `/scenarios` — the scenario simulator page (SIM-04).
 *
 * Layout:
 *   - Header row (title + History button)
 *   - Composer (freeform textarea, char counter, Submit)
 *   - Preset chips (category-grouped; click loads into composer, no auto-run)
 *   - Result area:
 *       • idle → hint copy
 *       • connecting/running → StreamStatus strip + spinner
 *       • result → SimulationView
 *       • error → destructive Alert + retry
 *
 * Streaming: `POST /api/scenarios/simulate` returns an SSE stream. We drive
 * it through the shared `useSse` hook, which auto-terminates on `complete` /
 * `error`. On `result` we snapshot the payload into `simulation` state and
 * append a history entry to sessionStorage-backed history.
 *
 * Suspense + AuthGuard + `dynamic = "force-dynamic"` mirror the pattern in
 * `app/briefing/page.tsx` — required so Next 15 doesn't try to prerender a
 * subtree that reads `useSearchParams()` inside `AuthGuard`.
 */

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Loader2, RefreshCw, Sparkles, Zap } from "lucide-react";

export const dynamic = "force-dynamic";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
	StreamStatus,
	type StreamStatusKind,
} from "@/components/briefing/stream-status";
import {
	HistoryPanel,
	HISTORY_MAX_ENTRIES,
	loadHistory,
	saveHistory,
	type ScenarioHistoryEntry,
} from "@/components/scenarios/history-panel";
import { PresetChips } from "@/components/scenarios/preset-chips";
import { ScenarioComposer } from "@/components/scenarios/scenario-composer";
import { SimulationView } from "@/components/scenarios/simulation-view";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useSse } from "@/hooks/use-sse";
import type { SseEvent } from "@/lib/api/client";
import {
	useScenarioPresets,
	type ScenarioSimulation,
	type ScenarioSseEvent,
} from "@/lib/api/scenarios";

export default function ScenariosPage() {
	return (
		<Suspense fallback={<PageSkeleton />}>
			<AuthGuard>
				<ScenariosInner />
			</AuthGuard>
		</Suspense>
	);
}

function PageSkeleton() {
	return (
		<main className="flex min-h-screen items-center justify-center">
			<Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
		</main>
	);
}

// ---------------------------------------------------------------------------
// SSE parse — reuse `useSse`'s parse hook to type each frame.
// ---------------------------------------------------------------------------

function parseScenarioFrame(raw: SseEvent): ScenarioSseEvent | null {
	try {
		const data = JSON.parse(raw.data);
		return { event: raw.event, data } as ScenarioSseEvent;
	} catch {
		return { event: raw.event, data: raw.data };
	}
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function ScenariosInner() {
	const [composerText, setComposerText] = useState("");
	// The scenario text that the currently-displayed simulation was run against.
	// Kept separate from composerText so a user can edit the composer without
	// clobbering the result panel's header.
	const [activeScenario, setActiveScenario] = useState<string | null>(null);
	const [simulation, setSimulation] = useState<ScenarioSimulation | null>(null);
	const [status, setStatus] = useState<StreamStatusKind>({ kind: "idle" });

	const [history, setHistory] = useState<ScenarioHistoryEntry[]>([]);
	const [historyOpen, setHistoryOpen] = useState(false);

	// Hydrate history from sessionStorage on mount.
	useEffect(() => {
		setHistory(loadHistory());
	}, []);

	// Persist history when it changes. `saveHistory` no-ops on server.
	useEffect(() => {
		saveHistory(history);
	}, [history]);

	const presets = useScenarioPresets({ enabled: true });

	// `body` for useSse changes as the composer text does — but the hook keys
	// `start` on its `body` reference, so we compute the payload lazily via a
	// ref inside `handleSubmit` to avoid re-creating `start` per keystroke.
	// However, useSse's start closure captures body at start-time; passing the
	// current composer text as the body when we invoke start is fine because
	// useSse reads `body` when it opens the stream. We rely on the memoized
	// body value being fresh at the moment of `start()`.
	const requestBody = useMemo(
		() => ({ scenario_text: composerText.trim() }),
		[composerText],
	);

	const sse = useSse<ScenarioSseEvent>({
		path: "/api/scenarios/simulate",
		method: "POST",
		body: requestBody,
		enabled: false,
		parse: parseScenarioFrame,
		onEvent: (evt) => {
			switch (evt.event) {
				case "node_started": {
					setStatus({ kind: "running", label: "Simulating…" });
					break;
				}
				case "node_completed": {
					const d = evt.data as { node?: string; duration_ms?: number } | null;
					const ms = d?.duration_ms ?? 0;
					setStatus({
						kind: "running",
						label: `Simulator done in ${ms}ms`,
					});
					break;
				}
				case "result": {
					const sim = evt.data as ScenarioSimulation;
					setSimulation(sim);
					setActiveScenario(sim.scenario_text);
					// Push to history — newest first, dedup by exact scenario_text,
					// cap at HISTORY_MAX_ENTRIES.
					setHistory((prev) => {
						const filtered = prev.filter(
							(h) => h.scenario_text !== sim.scenario_text,
						);
						const entry: ScenarioHistoryEntry = {
							id:
								typeof crypto !== "undefined" && "randomUUID" in crypto
									? crypto.randomUUID()
									: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
							scenario_text: sim.scenario_text,
							simulation: sim,
							created_at: new Date().toISOString(),
						};
						return [entry, ...filtered].slice(0, HISTORY_MAX_ENTRIES);
					});
					break;
				}
				case "complete": {
					setStatus({ kind: "done", label: "Simulation complete" });
					break;
				}
				case "error": {
					const msg =
						(evt.data as { message?: string } | null)?.message ??
						"Simulation failed";
					setStatus({ kind: "error", message: msg });
					break;
				}
				default:
					break;
			}
		},
	});

	const handleSubmit = useCallback(() => {
		const trimmed = composerText.trim();
		if (!trimmed) return;
		if (sse.connected) return;
		setSimulation(null);
		setActiveScenario(trimmed);
		setStatus({ kind: "connecting" });
		sse.start();
	}, [composerText, sse]);

	const handlePresetSelect = useCallback((text: string) => {
		// Load into composer; do NOT auto-submit. User confirms with Send.
		setComposerText(text);
	}, []);

	const handleReloadHistory = useCallback(
		(entry: ScenarioHistoryEntry) => {
			// Restore the composer, the active scenario, and the simulation panel
			// to what the user saw the first time. No re-run, no backend call.
			setComposerText(entry.scenario_text);
			setActiveScenario(entry.scenario_text);
			setSimulation(entry.simulation);
			setStatus({ kind: "done", label: "Reloaded from history" });
			setHistoryOpen(false);
		},
		[],
	);

	const handleClearHistory = useCallback(() => {
		setHistory([]);
	}, []);

	const handleRetry = useCallback(() => {
		// If the composer still holds the scenario that failed (nothing edited
		// since), re-submit as-is. Otherwise restore it — but bail on the
		// immediate start so the composer-fed request body has a chance to
		// re-memoize on the next render (React batches state updates).
		if (!activeScenario) return;
		if (composerText.trim() === activeScenario) {
			handleSubmit();
			return;
		}
		setComposerText(activeScenario);
		setSimulation(null);
		setStatus({
			kind: "running",
			label: "Reloaded scenario — click Simulate to retry.",
		});
	}, [activeScenario, composerText, handleSubmit]);

	return (
		<main className="mx-auto max-w-5xl px-6 py-10">
			<Header
				historyEntries={history}
				historyOpen={historyOpen}
				onHistoryOpenChange={setHistoryOpen}
				onReloadHistory={handleReloadHistory}
				onClearHistory={handleClearHistory}
			/>

			<div className="mt-8 space-y-6">
				<ScenarioComposer
					value={composerText}
					onChange={setComposerText}
					onSubmit={handleSubmit}
					streaming={sse.connected}
				/>

				<PresetChips
					presets={presets.data}
					isLoading={presets.isLoading}
					disabled={sse.connected}
					onSelect={(preset) => handlePresetSelect(preset.scenario_text)}
				/>
			</div>

			<div className="mt-10 space-y-6">
				{status.kind !== "idle" ? (
					<div className="flex flex-wrap items-center gap-2">
						<StreamStatus status={status} />
					</div>
				) : null}

				{status.kind === "error" ? (
					<Alert variant="destructive">
						<AlertTriangle className="h-4 w-4" />
						<AlertTitle>Simulation failed</AlertTitle>
						<AlertDescription>
							<p>{status.message}</p>
							<Button
								variant="outline"
								size="sm"
								className="mt-3"
								onClick={handleRetry}
								disabled={!activeScenario || sse.connected}
							>
								<RefreshCw className="mr-2 h-4 w-4" />
								Retry
							</Button>
						</AlertDescription>
					</Alert>
				) : null}

				{simulation ? (
					<SimulationView simulation={simulation} />
				) : sse.connected ? (
					<Card>
						<CardContent className="flex items-center justify-center gap-3 py-16 text-muted-foreground">
							<Loader2 className="h-4 w-4 animate-spin" />
							<span className="text-sm">
								Running scenario against your active portfolio…
							</span>
						</CardContent>
					</Card>
				) : status.kind === "error" ? null : (
					<IdleHint />
				)}
			</div>
		</main>
	);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Header({
	historyEntries,
	historyOpen,
	onHistoryOpenChange,
	onReloadHistory,
	onClearHistory,
}: {
	historyEntries: ScenarioHistoryEntry[];
	historyOpen: boolean;
	onHistoryOpenChange: (open: boolean) => void;
	onReloadHistory: (entry: ScenarioHistoryEntry) => void;
	onClearHistory: () => void;
}) {
	return (
		<div className="flex flex-wrap items-start justify-between gap-4">
			<div>
				<p className="flex items-center gap-2 text-xs uppercase tracking-widest text-muted-foreground">
					<Zap className="h-3.5 w-3.5" />
					<span>Scenarios</span>
				</p>
				<h1 className="mt-2 text-3xl font-semibold tracking-tight">
					What-if simulator
				</h1>
				<p className="mt-2 max-w-2xl text-sm text-muted-foreground">
					Describe a hypothetical macro or thematic event and Lumen will
					simulate its impact on your active portfolio — with per-position
					mechanisms, magnitude ranges, historical analogs, and the
					falsifiability check that would flip the read.
				</p>
			</div>
			<HistoryPanel
				entries={historyEntries}
				open={historyOpen}
				onOpenChange={onHistoryOpenChange}
				onReload={onReloadHistory}
				onClear={onClearHistory}
			/>
		</div>
	);
}

function IdleHint() {
	return (
		<Card>
			<CardContent className="flex flex-col items-center gap-3 py-16 text-center">
				<Sparkles className="h-8 w-8 text-muted-foreground" />
				<p className="max-w-md text-sm text-muted-foreground">
					Run a scenario to see the analysis. Type a hypothetical in the
					composer above, or pick a preset chip to get started.
				</p>
			</CardContent>
		</Card>
	);
}
