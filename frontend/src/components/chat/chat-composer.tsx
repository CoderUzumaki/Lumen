"use client";

/**
 * Bottom-of-thread message composer.
 *
 * Multi-line textarea + Send button.
 *   - Enter        → submit (if content non-empty and not already busy).
 *   - Shift+Enter  → newline.
 *   - Backend caps content at 4000 chars — we enforce the same on the client
 *     via `maxLength` on the textarea; a small counter appears once the user
 *     is within ~10% of the ceiling.
 *
 * The composer is controlled: the parent owns the string so it can clear it
 * on successful send and repopulate it on retry.
 */

import { useRef } from "react";
import { Loader2, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const MAX_LEN = 4000;

export function ChatComposer({
	value,
	onChange,
	onSubmit,
	disabled,
	sending,
}: {
	value: string;
	onChange: (v: string) => void;
	onSubmit: () => void;
	disabled?: boolean;
	sending?: boolean;
}) {
	const textareaRef = useRef<HTMLTextAreaElement | null>(null);

	const trimmed = value.trim();
	const canSend = trimmed.length > 0 && !disabled && !sending;
	const overCeiling = value.length >= MAX_LEN;
	const showCounter = value.length > MAX_LEN * 0.9;

	function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			if (canSend) {
				onSubmit();
			}
		}
	}

	function handleSubmit(e: React.FormEvent) {
		e.preventDefault();
		if (canSend) {
			onSubmit();
		}
	}

	return (
		<form
			onSubmit={handleSubmit}
			className="border-t border-border bg-background/95 px-4 py-4 sm:px-6"
		>
			<div className="mx-auto flex max-w-4xl flex-col gap-2">
				<div className="flex items-end gap-2 rounded-2xl border border-border bg-card p-2 shadow-sm focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/40">
					<textarea
						ref={textareaRef}
						value={value}
						onChange={(e) => onChange(e.target.value)}
						onKeyDown={handleKeyDown}
						placeholder="Ask about your portfolio, a cluster, or a specific ticker…"
						disabled={disabled}
						maxLength={MAX_LEN}
						rows={2}
						className={cn(
							"flex-1 resize-none bg-transparent px-2 py-1.5 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none disabled:cursor-not-allowed disabled:opacity-60",
							"min-h-[3.5rem] max-h-[16rem]",
						)}
					/>
					<Button
						type="submit"
						size="icon"
						disabled={!canSend}
						aria-label="Send message"
						className="shrink-0"
					>
						{sending ? (
							<Loader2 className="h-4 w-4 animate-spin" />
						) : (
							<Send className="h-4 w-4" />
						)}
					</Button>
				</div>
				<div className="flex items-center justify-between gap-3 px-1 text-[11px] text-muted-foreground">
					<span>
						<kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono text-[10px]">
							Enter
						</kbd>{" "}
						to send ·{" "}
						<kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono text-[10px]">
							Shift+Enter
						</kbd>{" "}
						for newline
					</span>
					{showCounter ? (
						<span
							className={cn(
								"font-mono tabular-nums",
								overCeiling && "text-destructive",
							)}
						>
							{value.length} / {MAX_LEN}
						</span>
					) : null}
				</div>
			</div>
		</form>
	);
}
