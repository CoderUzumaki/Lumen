"use client";

import Link from "next/link";
import { ArrowRight, Info } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import {
	canHaveImpact,
	formatRelativeTime,
	IMPACT_MIN_SCORE,
	type RelevantClusterRead,
} from "@/lib/api/news";
import { ScoreBar } from "@/components/news/score-bar";
import { SourceChip, dedupeSources } from "@/components/news/source-chip";

/**
 * A single row in the /news feed. The whole card is a link to the detail
 * page; the "Analyze impact" button is a nested `stopPropagation` link so it
 * routes independently (and can be disabled when the score is below the
 * impact-assessment threshold).
 *
 * Ticker badges come from `cluster.entity_tickers` (human-readable) — NOT
 * from `relevance.touched_position_ids`, which are opaque UUIDs.
 */
export function FeedRow({ item }: { item: RelevantClusterRead }) {
	const { cluster, relevance } = item;
	const href = `/news/${cluster.id}`;
	const sources = dedupeSources(cluster.items ?? []);
	const impactAvailable = canHaveImpact(relevance.score);
	const belowThresholdMsg = `Relevance below ${(IMPACT_MIN_SCORE * 100).toFixed(0)}% — impact assessment is only generated for clusters that materially affect your portfolio.`;

	return (
		<Link
			href={href}
			className={cn(
				"group block rounded-lg border border-border bg-card p-4 transition-colors",
				"hover:border-primary/50 hover:bg-accent/40 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring",
			)}
		>
			<div className="flex flex-col gap-3">
				<div className="flex items-start justify-between gap-3">
					<div className="flex-1 min-w-0">
						<h3 className="text-base font-medium leading-snug text-foreground">
							{cluster.canonical_title}
						</h3>
						{cluster.canonical_summary ? (
							<p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
								{cluster.canonical_summary}
							</p>
						) : null}
					</div>
					<ArrowRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
				</div>

				<div className="flex flex-wrap items-center gap-1.5">
					{cluster.entity_tickers.length > 0 ? (
						<span className="text-[10px] uppercase tracking-widest text-muted-foreground">
							affects:
						</span>
					) : null}
					{cluster.entity_tickers.map((ticker) => (
						<Badge
							key={ticker}
							variant="outline"
							className="font-mono text-[11px] uppercase"
						>
							{ticker}
						</Badge>
					))}
				</div>

				<ScoreBar score={relevance.score} label="Relevance" />

				<div className="flex flex-wrap items-center justify-between gap-2">
					<div className="flex flex-wrap items-center gap-1.5">
						{sources.map((s) => (
							<SourceChip key={s} source={s} />
						))}
						<span className="text-xs text-muted-foreground">
							{formatRelativeTime(cluster.last_seen_at)}
						</span>
					</div>

					{impactAvailable ? (
						<Button
							asChild
							size="sm"
							variant="secondary"
							onClick={(e) => e.stopPropagation()}
						>
							<Link href={href}>Analyze impact</Link>
						</Button>
					) : (
						<Tooltip>
							<TooltipTrigger asChild>
								<span
									// wrapping span so the disabled button still shows the tooltip
									onClick={(e) => {
										e.preventDefault();
										e.stopPropagation();
									}}
									className="inline-flex"
								>
									<Button
										size="sm"
										variant="secondary"
										disabled
										aria-disabled="true"
										className="pointer-events-none"
									>
										<Info className="mr-1.5 h-3.5 w-3.5" />
										Analyze impact
									</Button>
								</span>
							</TooltipTrigger>
							<TooltipContent className="max-w-xs">
								{belowThresholdMsg}
							</TooltipContent>
						</Tooltip>
					)}
				</div>
			</div>
		</Link>
	);
}
