"use client";

import { Badge } from "@/components/ui/badge";
import type { NewsSource } from "@/lib/api/news";

/**
 * A single-source chip rendered inside a feed row. Backend uses lowercase
 * short names ("newsapi", "gdelt", ...); we map to slightly friendlier
 * display labels while keeping the chip compact.
 */
const SOURCE_LABEL: Record<NewsSource, string> = {
	newsapi: "NewsAPI",
	marketaux: "Marketaux",
	gdelt: "GDELT",
	edgar: "EDGAR",
	rss: "RSS",
};

export function SourceChip({ source }: { source: NewsSource | string }) {
	const label = SOURCE_LABEL[source as NewsSource] ?? source;
	return (
		<Badge variant="secondary" className="text-[10px] font-normal uppercase tracking-wide">
			{label}
		</Badge>
	);
}

/**
 * Dedupe an item list into distinct sources so the row shows each provider at
 * most once. Feed rows can safely receive `items: []` — we render nothing.
 */
export function dedupeSources(items: { source: NewsSource | string }[]): string[] {
	const seen = new Set<string>();
	const out: string[] = [];
	for (const it of items) {
		if (!seen.has(it.source)) {
			seen.add(it.source);
			out.push(it.source);
		}
	}
	return out;
}
