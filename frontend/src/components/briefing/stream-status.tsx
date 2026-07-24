"use client";

/**
 * A small status strip that renders the current SSE state — "synthesizer
 * starting…", "synthesizer done in {ms}ms", "briefing generated", or an error
 * — in a consistent visual language. Rendered above the briefing sections
 * while a `Generate live` stream is running.
 */

import { CheckCircle2, Loader2, Radio, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

export type StreamStatusKind =
	| { kind: "idle" }
	| { kind: "connecting" }
	| { kind: "running"; label: string }
	| { kind: "done"; label: string }
	| { kind: "error"; message: string };

export function StreamStatus({ status }: { status: StreamStatusKind }) {
	if (status.kind === "idle") return null;

	let icon: React.ReactNode;
	let text: string;
	let tone = "border-border bg-card text-muted-foreground";

	switch (status.kind) {
		case "connecting":
			icon = <Loader2 className="h-3.5 w-3.5 animate-spin" />;
			text = "Connecting…";
			break;
		case "running":
			icon = <Radio className="h-3.5 w-3.5 animate-pulse text-primary" />;
			text = status.label;
			break;
		case "done":
			icon = <CheckCircle2 className="h-3.5 w-3.5 text-primary" />;
			text = status.label;
			break;
		case "error":
			icon = <XCircle className="h-3.5 w-3.5 text-destructive" />;
			text = status.message;
			tone = "border-destructive/40 bg-destructive/10 text-destructive";
			break;
	}

	return (
		<div
			className={cn(
				"inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs",
				tone,
			)}
			role="status"
			aria-live="polite"
		>
			{icon}
			<span>{text}</span>
		</div>
	);
}
