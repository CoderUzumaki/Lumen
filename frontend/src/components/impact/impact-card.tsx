"use client";

import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { formatScorePercent } from "@/lib/api/news";
import type { ImpactRead } from "@/lib/api/impact";
import { AnalogCard } from "@/components/impact/analog-card";
import { CitationList } from "@/components/impact/citation-panel";
import { MagnitudeBar } from "@/components/impact/magnitude-bar";
import { ScoreBar } from "@/components/news/score-bar";

/**
 * Full impact-assessment view. Rendered when a cached `ImpactRead` exists —
 * the "generating" and "not found" states are handled at the page level.
 *
 * Layout in reading order:
 *   1. Mechanism (why this news moves the position — prose)
 *   2. Magnitude range + timeframe + confidence
 *   3. Falsifiability callout (what would have to happen to invalidate the
 *      assessment) — visually distinct via the Alert component
 *   4. Citations (chips → side-sheet)
 *   5. Historical analogs (past events similar to this one, with outcomes)
 *   6. Affected-position count (UUIDs, no ticker join available here)
 */
export function ImpactCard({
	impact,
	onRegenerate,
	isRegenerating,
}: {
	impact: ImpactRead;
	onRegenerate?: () => void;
	isRegenerating?: boolean;
}) {
	return (
		<div className="space-y-6">
			<div className="flex items-start justify-between gap-3">
				<div>
					<p className="text-xs uppercase tracking-widest text-muted-foreground">
						Impact assessment
					</p>
					<h2 className="mt-1 text-xl font-semibold tracking-tight">
						Mechanism
					</h2>
				</div>
				{onRegenerate ? (
					<Button
						variant="outline"
						size="sm"
						onClick={onRegenerate}
						disabled={isRegenerating}
					>
						{isRegenerating ? (
							<Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
						) : (
							<RefreshCw className="mr-2 h-3.5 w-3.5" />
						)}
						Regenerate
					</Button>
				) : null}
			</div>

			<div className="space-y-3 whitespace-pre-line text-sm leading-relaxed text-foreground">
				{impact.mechanism}
			</div>

			<Separator />

			<div className="grid gap-4 sm:grid-cols-2">
				<div className="sm:col-span-2">
					<MagnitudeBar low={impact.magnitude_low} high={impact.magnitude_high} />
				</div>

				<div>
					<p className="text-xs uppercase tracking-widest text-muted-foreground">
						Timeframe
					</p>
					<div className="mt-1">
						{impact.timeframe_days === null ? (
							<Badge variant="secondary">no timeframe</Badge>
						) : (
							<Badge variant="secondary" className="text-xs">
								{impact.timeframe_days} day{impact.timeframe_days === 1 ? "" : "s"}
							</Badge>
						)}
					</div>
				</div>

				<div>
					<p className="text-xs uppercase tracking-widest text-muted-foreground">
						Confidence
					</p>
					<div className="mt-1">
						<ScoreBar
							score={impact.confidence}
							label={formatScorePercent(impact.confidence)}
						/>
					</div>
				</div>
			</div>

			<Alert>
				<AlertTriangle className="h-4 w-4" />
				<AlertTitle>Falsifiability</AlertTitle>
				<AlertDescription>{impact.falsifiability}</AlertDescription>
			</Alert>

			<Separator />

			<section>
				<p className="mb-2 text-xs uppercase tracking-widest text-muted-foreground">
					Citations
				</p>
				<CitationList citations={impact.citations} />
			</section>

			{impact.historical_analogs.length > 0 ? (
				<>
					<Separator />
					<section>
						<p className="mb-2 text-xs uppercase tracking-widest text-muted-foreground">
							Historical analogs
						</p>
						<div className="grid gap-2 sm:grid-cols-2">
							{impact.historical_analogs.map((a, i) => (
								<AnalogCard key={`${a.when}-${i}`} analog={a} />
							))}
						</div>
					</section>
				</>
			) : null}

			<Separator />

			<section className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
				<div>
					Affects{" "}
					<span className="font-mono tabular-nums text-foreground">
						{impact.affected_positions.length}
					</span>{" "}
					position{impact.affected_positions.length === 1 ? "" : "s"}
				</div>
				<div className="font-mono">
					Generated{" "}
					{new Date(impact.created_at).toLocaleString(undefined, {
						dateStyle: "medium",
						timeStyle: "short",
					})}
				</div>
			</section>
		</div>
	);
}
