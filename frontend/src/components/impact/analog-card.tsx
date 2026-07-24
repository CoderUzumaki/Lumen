"use client";

import { Badge } from "@/components/ui/badge";
import type { HistoricalAnalog } from "@/lib/api/impact";
import { formatShortDate } from "@/lib/api/news";

/**
 * A single historical-analog card: "here's a past event similar to this news,
 * and here's what happened afterward". Similarity score is 0..1, backend-
 * assigned by the analog-retrieval step.
 */
export function AnalogCard({ analog }: { analog: HistoricalAnalog }) {
	const similarityPct = Math.round(
		Math.max(0, Math.min(1, analog.similarity_score)) * 100,
	);
	return (
		<div className="rounded-md border border-border bg-card/50 p-3">
			<div className="flex items-start justify-between gap-2">
				<div className="flex-1 min-w-0">
					<p className="text-sm font-medium leading-snug text-foreground">
						{analog.event_description}
					</p>
					<p className="mt-0.5 text-xs text-muted-foreground">
						{formatShortDate(analog.when)}
					</p>
				</div>
				<Badge variant="secondary" className="font-mono tabular-nums text-[10px]">
					{similarityPct}% similar
				</Badge>
			</div>
			<p className="mt-2 text-sm text-muted-foreground">
				{analog.outcome_description}
			</p>
		</div>
	);
}
