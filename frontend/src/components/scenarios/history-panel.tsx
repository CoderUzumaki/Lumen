"use client";

/**
 * Session-scoped simulation history side panel.
 *
 * The `/api/scenarios/simulate` endpoint doesn't persist simulations — per
 * SIM-01 comments in `backend/app/routes/scenarios.py`, it's a stream, not a
 * write. So we keep a lightweight per-session log in `sessionStorage` (survives
 * hard-refresh, dies on tab close) capped at 20 entries.
 *
 * Each entry stores the full simulation payload so "Reload" restores the exact
 * result the user saw — no re-runs and no backend round-trip.
 */

import { History, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
	SheetTrigger,
} from "@/components/ui/sheet";
import type { ScenarioSimulation } from "@/lib/api/scenarios";

export type ScenarioHistoryEntry = {
	id: string;
	scenario_text: string;
	simulation: ScenarioSimulation;
	created_at: string; // ISO
};

export const HISTORY_STORAGE_KEY = "lumen:scenario:history";
export const HISTORY_MAX_ENTRIES = 20;

/**
 * Load persisted history from sessionStorage. Silently returns `[]` on any
 * parse error / access failure (e.g. Safari private mode) — history is
 * best-effort, never fatal.
 */
export function loadHistory(): ScenarioHistoryEntry[] {
	if (typeof window === "undefined") return [];
	try {
		const raw = window.sessionStorage.getItem(HISTORY_STORAGE_KEY);
		if (!raw) return [];
		const parsed = JSON.parse(raw);
		if (!Array.isArray(parsed)) return [];
		// Cheap runtime guard — drop anything without the required top-level keys.
		return parsed.filter(
			(e): e is ScenarioHistoryEntry =>
				typeof e === "object" &&
				e !== null &&
				typeof e.id === "string" &&
				typeof e.scenario_text === "string" &&
				typeof e.simulation === "object" &&
				e.simulation !== null,
		);
	} catch {
		return [];
	}
}

export function saveHistory(entries: ScenarioHistoryEntry[]): void {
	if (typeof window === "undefined") return;
	try {
		window.sessionStorage.setItem(
			HISTORY_STORAGE_KEY,
			JSON.stringify(entries.slice(0, HISTORY_MAX_ENTRIES)),
		);
	} catch {
		// Quota / privacy-mode failures aren't user-facing; swallow.
	}
}

function truncate(text: string, max = 120): string {
	if (text.length <= max) return text;
	return `${text.slice(0, max - 1).trimEnd()}…`;
}

function formatTime(iso: string): string {
	try {
		return new Date(iso).toLocaleString(undefined, {
			month: "short",
			day: "numeric",
			hour: "numeric",
			minute: "2-digit",
		});
	} catch {
		return iso;
	}
}

export function HistoryPanel({
	entries,
	open,
	onOpenChange,
	onReload,
	onClear,
}: {
	entries: ScenarioHistoryEntry[];
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onReload: (entry: ScenarioHistoryEntry) => void;
	onClear: () => void;
}) {
	return (
		<Sheet open={open} onOpenChange={onOpenChange}>
			<SheetTrigger asChild>
				<Button variant="outline" size="sm">
					<History className="mr-2 h-4 w-4" />
					History
					{entries.length > 0 ? (
						<Badge
							variant="secondary"
							className="ml-2 font-mono tabular-nums text-[10px]"
						>
							{entries.length}
						</Badge>
					) : null}
				</Button>
			</SheetTrigger>
			<SheetContent side="right" className="w-full sm:max-w-md">
				<SheetHeader>
					<SheetTitle>Simulation history</SheetTitle>
					<SheetDescription>
						This session only — up to {HISTORY_MAX_ENTRIES} recent scenarios.
					</SheetDescription>
				</SheetHeader>

				{entries.length === 0 ? (
					<div className="flex-1 px-4 pb-6">
						<p className="text-sm text-muted-foreground">
							No simulations yet. Run one from the composer to see it here.
						</p>
					</div>
				) : (
					<>
						<div className="flex-1 overflow-y-auto px-4 pb-4">
							<ul className="space-y-3">
								{entries.map((entry) => (
									<li
										key={entry.id}
										className="rounded-md border border-border bg-card/60 p-3"
									>
										<p className="text-xs text-muted-foreground">
											{formatTime(entry.created_at)}
										</p>
										<p className="mt-1 text-sm leading-relaxed text-foreground">
											{truncate(entry.scenario_text)}
										</p>
										<div className="mt-3 flex justify-end">
											<Button
												variant="outline"
												size="sm"
												onClick={() => onReload(entry)}
											>
												<RefreshCw className="mr-2 h-3.5 w-3.5" />
												Reload
											</Button>
										</div>
									</li>
								))}
							</ul>
						</div>
						<div className="mt-auto border-t border-border p-4">
							<Button
								variant="ghost"
								size="sm"
								onClick={onClear}
								className="text-muted-foreground"
							>
								Clear history
							</Button>
						</div>
					</>
				)}
			</SheetContent>
		</Sheet>
	);
}
