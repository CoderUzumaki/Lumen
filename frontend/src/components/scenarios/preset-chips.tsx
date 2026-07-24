"use client";

/**
 * Preset chip row grouped by category ("monetary", "macro", "commodity",
 * "thematic", "geopolitical", "crypto", …). One click on a chip loads the
 * preset's `scenario_text` into the composer — the user still hits Send
 * explicitly. This mirrors SIM-03's intent: presets are a shortcut, not
 * auto-run.
 *
 * We group by whatever `category` values the backend returns rather than
 * hard-coding a list — new categories added server-side render automatically.
 */

import { Loader2, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { ScenarioPreset } from "@/lib/api/scenarios";
import { cn } from "@/lib/utils";

// Human-friendly category labels. Falls back to the raw key if unknown so
// the UI never breaks on a new backend category.
const CATEGORY_LABELS: Record<string, string> = {
	monetary: "Monetary",
	macro: "Macro",
	commodity: "Commodity",
	thematic: "Thematic",
	geopolitical: "Geopolitical",
	crypto: "Crypto",
};

function formatCategory(cat: string): string {
	if (CATEGORY_LABELS[cat]) return CATEGORY_LABELS[cat];
	return cat.charAt(0).toUpperCase() + cat.slice(1);
}

export function PresetChips({
	presets,
	isLoading,
	disabled,
	onSelect,
}: {
	presets: ScenarioPreset[] | undefined;
	isLoading: boolean;
	disabled?: boolean;
	onSelect: (preset: ScenarioPreset) => void;
}) {
	if (isLoading) {
		return (
			<div className="flex items-center gap-2 text-xs text-muted-foreground">
				<Loader2 className="h-3.5 w-3.5 animate-spin" />
				Loading presets…
			</div>
		);
	}

	if (!presets || presets.length === 0) {
		return (
			<p className="text-xs text-muted-foreground">
				No preset scenarios available.
			</p>
		);
	}

	// Group by `category`, preserving insertion order (Map keeps insertion order).
	const grouped = new Map<string, ScenarioPreset[]>();
	for (const p of presets) {
		const bucket = grouped.get(p.category) ?? [];
		bucket.push(p);
		grouped.set(p.category, bucket);
	}

	return (
		<div className="space-y-3">
			<div className="flex items-center gap-2 text-xs uppercase tracking-widest text-muted-foreground">
				<Sparkles className="h-3.5 w-3.5" />
				<span>Preset scenarios</span>
			</div>
			<div className="space-y-2.5">
				{Array.from(grouped.entries()).map(([category, items]) => (
					<div key={category} className="flex flex-wrap items-center gap-2">
						<Badge variant="outline" className="shrink-0 text-[10px] uppercase tracking-wider">
							{formatCategory(category)}
						</Badge>
						{items.map((preset) => (
							<button
								key={preset.id}
								type="button"
								disabled={disabled}
								onClick={() => onSelect(preset)}
								className={cn(
									"inline-flex items-center rounded-full border border-border bg-secondary/40 px-3 py-1 text-xs text-muted-foreground transition-colors",
									"hover:border-primary/60 hover:bg-secondary hover:text-foreground",
									"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring",
									"disabled:opacity-50 disabled:pointer-events-none",
								)}
								title={preset.scenario_text}
							>
								{preset.title}
							</button>
						))}
					</div>
				))}
			</div>
		</div>
	);
}
