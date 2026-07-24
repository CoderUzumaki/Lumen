"use client";

/**
 * Small pill that renders inline with an assistant bubble when the backend
 * emits a `tool_call` / `tool_result` SSE frame.
 *
 * As of CHAT-04 the backend does NOT emit these events (see the deviation
 * note in `backend/app/routes/chat.py`'s docstring — the graph is currently
 * single-await and only emits `token` / `citations` / `done`). The chat
 * page's SSE parser accepts + ignores those events silently for
 * forward-compat, so this component is currently unused; it exists so a
 * future CHAT-03 refactor emitting real tool events has a matching render
 * without another patch to the chat page.
 */

import { Wrench } from "lucide-react";

import { Badge } from "@/components/ui/badge";

export type ToolBadgeStatus = "calling" | "done" | "error";

export function ToolBadge({
	name,
	status,
}: {
	name: string;
	status: ToolBadgeStatus;
}) {
	const label =
		status === "calling"
			? `Calling ${name}…`
			: status === "error"
				? `${name} failed`
				: `Called ${name}`;
	return (
		<Badge
			variant="secondary"
			className="gap-1 font-mono text-[10px] uppercase tracking-wide"
		>
			<Wrench className="h-3 w-3" />
			{label}
		</Badge>
	);
}
