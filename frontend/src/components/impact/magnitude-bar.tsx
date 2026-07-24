"use client";

import { formatSignedPercent } from "@/lib/api/news";

/**
 * Magnitude range visual: a horizontal bar spanning `magnitude_low` →
 * `magnitude_high`. The full track is [-25%, +25%] (a wide window so most
 * plausible single-cluster impacts fit inside), the fill covers the low→high
 * interval, and a zero-line tick anchors the reader.
 *
 * Both endpoints may be null — the backend leaves them empty when the model
 * declines to commit a range. We render "Range not established" in that case.
 */
export function MagnitudeBar({
	low,
	high,
}: {
	low: string | null;
	high: string | null;
}) {
	if (low === null && high === null) {
		return (
			<div className="rounded-md border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">
				Range not established
			</div>
		);
	}

	const lowN = low === null ? null : Number(low);
	const highN = high === null ? null : Number(high);
	// Fall back to a single endpoint if only one side is given.
	const lo = lowN ?? highN ?? 0;
	const hi = highN ?? lowN ?? 0;
	const [rangeLo, rangeHi] = lo <= hi ? [lo, hi] : [hi, lo];

	// Fixed axis so multiple assessments are visually comparable at a glance.
	const AXIS_MIN = -0.25;
	const AXIS_MAX = 0.25;
	const axisSpan = AXIS_MAX - AXIS_MIN;
	const clamp = (n: number) => Math.max(AXIS_MIN, Math.min(AXIS_MAX, n));
	const leftPct = ((clamp(rangeLo) - AXIS_MIN) / axisSpan) * 100;
	const rightPct = ((clamp(rangeHi) - AXIS_MIN) / axisSpan) * 100;
	const widthPct = Math.max(1.5, rightPct - leftPct);
	const zeroPct = ((0 - AXIS_MIN) / axisSpan) * 100;

	return (
		<div>
			<div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
				<span>Estimated magnitude</span>
				<span className="font-mono tabular-nums text-foreground">
					{formatSignedPercent(low)} to {formatSignedPercent(high)}
				</span>
			</div>
			<div className="relative h-3 w-full overflow-hidden rounded-full bg-secondary">
				{/* zero-line tick */}
				<div
					className="absolute top-0 h-full w-px bg-border"
					style={{ left: `${zeroPct}%` }}
					aria-hidden
				/>
				<div
					className="absolute top-0 h-full rounded-full bg-primary"
					style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
					role="img"
					aria-label={`Magnitude range: ${formatSignedPercent(low)} to ${formatSignedPercent(high)}`}
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
