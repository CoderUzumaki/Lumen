"use client";

/**
 * Scrollable message column for a chat session.
 *
 * `messages` includes both persisted messages (from the GET-session query) and
 * transient client-only entries (the optimistic user echo + placeholder
 * assistant). The parent keeps IDs stable across the swap so React doesn't
 * re-mount bubbles when the server row lands.
 *
 * Auto-scroll: on every messages-array change, we scroll the bottom sentinel
 * into view. That keeps the newest message visible during streaming without
 * fighting the user if they scroll up (browsers only nudge if the scroll
 * container was already near bottom).
 */

import { useEffect, useRef } from "react";

import { MessageBubble, type BubbleMessage } from "./message-bubble";

export function MessageList({
	messages,
	onRetry,
}: {
	messages: BubbleMessage[];
	onRetry?: (id: string) => void;
}) {
	const bottomRef = useRef<HTMLDivElement | null>(null);

	useEffect(() => {
		bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
	}, [messages]);

	return (
		<div className="flex flex-col gap-6 px-4 py-6 sm:px-6">
			{messages.map((m) => (
				<MessageBubble
					key={m.id}
					message={m}
					onRetry={onRetry ? () => onRetry(m.id) : undefined}
				/>
			))}
			<div ref={bottomRef} className="h-1" aria-hidden />
		</div>
	);
}
