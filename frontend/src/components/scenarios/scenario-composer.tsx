"use client";

/**
 * Freeform scenario input. Backend enforces `min_length=1, max_length=2000`
 * (see `ScenarioSimulateRequest` in backend/app/schemas/scenario.py); we mirror
 * that here so users get instant feedback instead of a 422 round-trip.
 *
 * Presets fill the textarea via `value` control — that's why we lift state to
 * the parent. Submit is disabled while a stream is in-flight (parent passes
 * `streaming`) so a user can't fire a second POST mid-simulation.
 */

import { useEffect, useState } from "react";
import { Loader2, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const MIN_LENGTH = 1;
export const MAX_LENGTH = 2000;

export function ScenarioComposer({
	value,
	onChange,
	onSubmit,
	streaming,
}: {
	value: string;
	onChange: (next: string) => void;
	onSubmit: () => void;
	streaming: boolean;
}) {
	const trimmed = value.trim();
	const tooShort = trimmed.length < MIN_LENGTH;
	const tooLong = value.length > MAX_LENGTH;
	const disabled = streaming || tooShort || tooLong;

	// `navigator` isn't available on the server. Compute the mod-key hint after
	// mount so we don't hydration-mismatch.
	const [isMac, setIsMac] = useState(false);
	useEffect(() => {
		setIsMac(navigator.platform.toLowerCase().includes("mac"));
	}, []);

	const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
		// Cmd/Ctrl + Enter submits — matches most chat composers on the site.
		if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !disabled) {
			e.preventDefault();
			onSubmit();
		}
	};

	return (
		<div className="rounded-lg border border-border bg-card p-4">
			<label
				htmlFor="scenario-composer"
				className="text-xs uppercase tracking-widest text-muted-foreground"
			>
				Describe a scenario
			</label>
			<textarea
				id="scenario-composer"
				value={value}
				onChange={(e) => onChange(e.target.value)}
				onKeyDown={handleKeyDown}
				disabled={streaming}
				placeholder="What if the Fed cuts 50bps at next FOMC? What if oil hits $120?"
				rows={4}
				className={cn(
					"mt-2 w-full resize-none rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none transition-[color,box-shadow]",
					"placeholder:text-muted-foreground",
					"focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
					"disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
					"dark:bg-input/30",
					tooLong && "border-destructive focus-visible:ring-destructive/30",
				)}
				aria-invalid={tooLong ? true : undefined}
			/>
			<div className="mt-3 flex items-center justify-between gap-3">
				<div
					className={cn(
						"text-xs font-mono tabular-nums",
						tooLong ? "text-destructive" : "text-muted-foreground",
					)}
					aria-live="polite"
				>
					{value.length.toLocaleString()} / {MAX_LENGTH.toLocaleString()}
				</div>
				<div className="flex items-center gap-2 text-xs text-muted-foreground">
					<span className="hidden sm:inline">
						<kbd className="rounded border border-border bg-secondary/40 px-1.5 py-0.5 font-mono text-[10px]">
							{isMac ? "⌘" : "Ctrl"}
						</kbd>
						{" + "}
						<kbd className="rounded border border-border bg-secondary/40 px-1.5 py-0.5 font-mono text-[10px]">
							Enter
						</kbd>
					</span>
					<Button
						onClick={onSubmit}
						disabled={disabled}
						size="sm"
					>
						{streaming ? (
							<>
								<Loader2 className="mr-2 h-4 w-4 animate-spin" />
								Simulating…
							</>
						) : (
							<>
								<Send className="mr-2 h-4 w-4" />
								Simulate
							</>
						)}
					</Button>
				</div>
			</div>
		</div>
	);
}
