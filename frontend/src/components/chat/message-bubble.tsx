"use client";

/**
 * One rendered chat message. Layout differs by role:
 *
 * - `user`      — right-aligned, primary background, plain text (no markdown
 *                 render — prevents user pastes containing `# hi` from being
 *                 promoted to a heading).
 * - `assistant` — left-aligned, muted background, markdown-rendered via
 *                 react-markdown. Citation chips (if any) render directly
 *                 below the bubble.
 * - `system`    — treated visually like an assistant message but with a
 *                 subtle badge; system messages rarely surface to the UI
 *                 today but we keep the render path so debug/prompt-visibility
 *                 features can land without another patch.
 *
 * `pending: true` renders a spinner + "thinking…" placeholder in place of the
 * content. Used for the optimistic assistant placeholder while the SSE stream
 * is opening.
 *
 * `error` is a client-side flag for assistant messages that failed mid-stream
 * — renders a destructive-tinted bubble with a retry button (hooked by the
 * caller via `onRetry`).
 */

import { AlertTriangle, Bot, Loader2, RefreshCw, User } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ChatMessageRead, ChatRole } from "@/lib/api/chat";
import { CitationChips } from "./citation-chips";

export type BubbleMessage = ChatMessageRead & {
	/** True while we're waiting for the first `token` frame. */
	pending?: boolean;
	/** True if the stream errored out — caller should offer `onRetry`. */
	error?: boolean;
	/** Human-readable error text; only shown when `error` is true. */
	errorMessage?: string;
};

export function MessageBubble({
	message,
	onRetry,
}: {
	message: BubbleMessage;
	onRetry?: () => void;
}) {
	const isUser = message.role === "user";
	const isAssistant = message.role === "assistant";
	const isSystem = message.role === "system";

	return (
		<div
			className={cn(
				"flex gap-3",
				isUser ? "flex-row-reverse" : "flex-row",
			)}
		>
			<Avatar role={message.role} />
			<div
				className={cn(
					"flex min-w-0 flex-1 flex-col",
					isUser ? "items-end" : "items-start",
				)}
			>
				<div
					className={cn(
						"max-w-[85ch] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm",
						isUser && "bg-primary text-primary-foreground",
						(isAssistant || isSystem) &&
							!message.error &&
							"bg-muted text-foreground",
						message.error &&
							"border border-destructive/40 bg-destructive/10 text-foreground",
					)}
				>
					{message.pending ? (
						<span className="inline-flex items-center gap-2 text-muted-foreground">
							<Loader2 className="h-3.5 w-3.5 animate-spin" />
							thinking…
						</span>
					) : message.error ? (
						<div className="flex items-start gap-2">
							<AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
							<div>
								<p className="font-medium">Could not generate a reply.</p>
								{message.errorMessage ? (
									<p className="mt-1 text-xs text-muted-foreground">
										{message.errorMessage}
									</p>
								) : null}
								{onRetry ? (
									<Button
										variant="outline"
										size="sm"
										className="mt-3"
										onClick={onRetry}
									>
										<RefreshCw className="mr-2 h-3.5 w-3.5" />
										Retry
									</Button>
								) : null}
							</div>
						</div>
					) : isUser ? (
						// User content stays plain-text: whitespace preserved, no markdown.
						<p className="whitespace-pre-wrap break-words">
							{message.content}
						</p>
					) : (
						<div className="markdown-body break-words">
							<ReactMarkdown>{message.content}</ReactMarkdown>
						</div>
					)}
				</div>

				{isAssistant && !message.pending && !message.error ? (
					<CitationChips citations={message.citations ?? []} />
				) : null}
			</div>
		</div>
	);
}

function Avatar({ role }: { role: ChatRole }) {
	const isUser = role === "user";
	return (
		<div
			className={cn(
				"flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
				isUser
					? "border-primary/40 bg-primary/10 text-primary"
					: "border-border bg-card text-muted-foreground",
			)}
			aria-hidden
		>
			{isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
		</div>
	);
}
