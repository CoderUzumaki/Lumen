"use client";

import { cn } from "@/lib/utils";
import { formatScorePercent, scoreToPercent } from "@/lib/api/news";

/**
 * Horizontal 0..1 progress-bar. `score` accepts the wire-format Decimal string
 * ("0.435") or a plain number. Track uses `bg-secondary`, fill uses
 * `bg-primary` per the theme tokens.
 */
export function ScoreBar({
	score,
	label,
	className,
}: {
	score: string | number | null | undefined;
	label?: string;
	className?: string;
}) {
	const pct = scoreToPercent(score);
	return (
		<div className={cn("w-full", className)}>
			{label ? (
				<div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
					<span>{label}</span>
					<span className="font-mono tabular-nums text-foreground">
						{formatScorePercent(score)}
					</span>
				</div>
			) : null}
			<div
				className="h-1.5 w-full overflow-hidden rounded-full bg-secondary"
				role="progressbar"
				aria-valuemin={0}
				aria-valuemax={100}
				aria-valuenow={Math.round(pct)}
				aria-label={label ?? "Score"}
			>
				<div
					className="h-full rounded-full bg-primary transition-[width]"
					style={{ width: `${pct}%` }}
				/>
			</div>
		</div>
	);
}
