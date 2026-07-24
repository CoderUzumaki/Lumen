"use client";

/**
 * One per-position card inside a `ScenarioSimulation`.
 *
 * The visual mirrors `components/impact/magnitude-bar.tsx` — same fixed
 * -25%/+25% axis so scenario magnitudes are visually comparable across cards
 * and across pages. We don't reuse that component directly because it takes
 * Decimal-string endpoints (news impacts), whereas scenario magnitudes are
 * plain JS `number` fields per the SIM-02 schema.
 */

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	formatScorePercent,
	formatSignedPercent,
} from "@/lib/api/news";
import type { PositionImpact } from "@/lib/api/scenarios";
import { cn } from "@/lib/utils";

/**
 * Number-mode magnitude bar. Same visual language as
 * `components/impact/magnitude-bar.tsx`, but accepts `number | null` (scenario
 * schema) instead of `string | null` (impact schema).
 */
function ScenarioMagnitudeBar({
	low,
	high,
}: {
	low: number | null;
	high: number | null;
}) {
	if (low === null && high === null) {
		return (
			<div className="rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
				Range not established
			</div>
		);
	}

	const lo = low ?? high ?? 0;
	const hi = high ?? low ?? 0;
	const [rangeLo, rangeHi] = lo <= hi ? [lo, hi] : [hi, lo];

	const AXIS_MIN = -0.25;
	const AXIS_MAX = 0.25;
	const axisSpan = AXIS_MAX - AXIS_MIN;
	const clamp = (n: number) => Math.max(AXIS_MIN, Math.min(AXIS_MAX, n));
	const leftPct = ((clamp(rangeLo) - AXIS_MIN) / axisSpan) * 100;
	const rightPct = ((clamp(rangeHi) - AXIS_MIN) / axisSpan) * 100;
	const widthPct = Math.max(1.5, rightPct - leftPct);
	const zeroPct = ((0 - AXIS_MIN) / axisSpan) * 100;

	// String-fed formatter — pass the numeric endpoints through as strings so
	// the shared helper's null-guard and "—" fallback still apply.
	const lowLabel = low === null ? null : String(low);
	const highLabel = high === null ? null : String(high);

	return (
		<div>
			<div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
				<span>Estimated magnitude</span>
				<span className="font-mono tabular-nums text-foreground">
					{formatSignedPercent(lowLabel)} to {formatSignedPercent(highLabel)}
				</span>
			</div>
			<div className="relative h-3 w-full overflow-hidden rounded-full bg-secondary">
				<div
					className="absolute top-0 h-full w-px bg-border"
					style={{ left: `${zeroPct}%` }}
					aria-hidden
				/>
				<div
					className="absolute top-0 h-full rounded-full bg-primary"
					style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
					role="img"
					aria-label={`Magnitude range: ${formatSignedPercent(lowLabel)} to ${formatSignedPercent(highLabel)}`}
				/>
			</div>
			<div className="mt-1 flex justify-between text-[10px] uppercase tracking-widest text-muted-foreground">
				<span>-25%</span>
				<span>0%</span>
				<span>+25%</span>
			</div>
		</div>
	);
}

function ConfidenceBar({ confidence }: { confidence: number }) {
	// confidence is 0..1 per the SIM-02 schema (Field(ge=0.0, le=1.0)).
	const clamped = Math.max(0, Math.min(1, confidence));
	const pct = clamped * 100;
	return (
		<div>
			<div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
				<span>Confidence</span>
				<span className="font-mono tabular-nums text-foreground">
					{formatScorePercent(confidence)}
				</span>
			</div>
			<div className="relative h-2 w-full overflow-hidden rounded-full bg-secondary">
				<div
					className={cn(
						"absolute top-0 left-0 h-full rounded-full bg-primary",
					)}
					style={{ width: `${pct}%` }}
					role="progressbar"
					aria-valuenow={Math.round(pct)}
					aria-valuemin={0}
					aria-valuemax={100}
				/>
			</div>
		</div>
	);
}

export function PositionImpactCard({ impact }: { impact: PositionImpact }) {
	return (
		<Card>
			<CardHeader className="pb-3">
				<div className="flex items-center justify-between gap-2">
					<CardTitle className="font-mono text-base tracking-tight">
						{impact.ticker}
					</CardTitle>
					<Badge variant="secondary" className="font-mono tabular-nums text-[10px]">
						{formatScorePercent(impact.confidence)} conf.
					</Badge>
				</div>
			</CardHeader>
			<CardContent className="space-y-4">
				<p className="whitespace-pre-line text-sm leading-relaxed text-foreground">
					{impact.mechanism}
				</p>
				<ScenarioMagnitudeBar
					low={impact.magnitude_low}
					high={impact.magnitude_high}
				/>
				<ConfidenceBar confidence={impact.confidence} />
			</CardContent>
		</Card>
	);
}
