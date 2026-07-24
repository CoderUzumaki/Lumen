"use client";

/**
 * Card for a single `BriefingItem` (a top-mover or watchlist entry).
 *
 * Deviation from BUILD.md: the item card is supposed to link to
 * `/news/[cluster_id]`, but the briefing schema exposes `impact_id`, not
 * `cluster_id`. Until the backend threads `cluster_id` through the briefing
 * schema, the card links to the news feed (`/news`) instead of the cluster
 * detail page. A tooltip on the title explains the current limitation.
 */

import Link from "next/link";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { BriefingItem } from "@/lib/api/briefings";

export function BriefingItemCard({ item }: { item: BriefingItem }) {
	const [open, setOpen] = useState(false);
	const pct = Math.round(Math.max(0, Math.min(1, item.confidence)) * 100);
	return (
		<Card>
			<CardHeader className="pb-3">
				<div className="flex items-start justify-between gap-3">
					<Tooltip>
						<TooltipTrigger asChild>
							<Link
								href="/news"
								className="text-base font-semibold leading-snug hover:underline"
							>
								{item.cluster_title}
							</Link>
						</TooltipTrigger>
						<TooltipContent side="top" className="max-w-xs">
							Full detail linkable once cluster_id is threaded through the
							briefing schema.
						</TooltipContent>
					</Tooltip>
					<div className="shrink-0 text-right">
						<div className="text-[10px] uppercase tracking-widest text-muted-foreground">
							Confidence
						</div>
						<div className="mt-0.5 text-sm font-semibold tabular-nums">
							{pct}%
						</div>
					</div>
				</div>
				<p className="mt-2 text-sm text-muted-foreground">
					{item.one_line_summary}
				</p>
			</CardHeader>
			<CardContent className="space-y-3">
				<div>
					<div
						className="h-1.5 w-full overflow-hidden rounded-full bg-secondary"
						role="progressbar"
						aria-valuenow={pct}
						aria-valuemin={0}
						aria-valuemax={100}
						aria-label={`Confidence ${pct}%`}
					>
						<div
							className="h-full rounded-full bg-primary transition-all"
							style={{ width: `${pct}%` }}
						/>
					</div>
				</div>

				{item.affected_positions.length > 0 ? (
					<div className="flex flex-wrap items-center gap-1.5">
						<span className="text-[10px] uppercase tracking-widest text-muted-foreground">
							Affects
						</span>
						{item.affected_positions.map((t) => (
							<Badge key={t} variant="secondary" className="font-mono text-xs">
								{t}
							</Badge>
						))}
					</div>
				) : null}

				<Collapsible open={open} onOpenChange={setOpen}>
					<CollapsibleTrigger
						className={cn(
							"flex w-full items-center gap-1.5 text-left text-xs font-medium",
							"text-muted-foreground hover:text-foreground transition-colors",
						)}
					>
						{open ? (
							<ChevronDown className="h-3.5 w-3.5" />
						) : (
							<ChevronRight className="h-3.5 w-3.5" />
						)}
						Mechanism
					</CollapsibleTrigger>
					<CollapsibleContent className="pt-2 text-sm leading-relaxed text-muted-foreground">
						{item.mechanism_summary}
					</CollapsibleContent>
				</Collapsible>
			</CardContent>
		</Card>
	);
}
