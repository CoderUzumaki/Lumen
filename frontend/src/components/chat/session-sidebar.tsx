"use client";

/**
 * Left column of the /chat surface. Lists every chat session for the caller,
 * ordered newest-first (backend already sorts on `updated_at desc`), plus:
 *
 *   - a "New chat" button that POSTs an empty session and navigates the
 *     caller to `/chat/<new id>`,
 *   - a trash icon per row that DELETEs the session (with a `confirm()`
 *     prompt because there's no undo),
 *   - an active-row highlight when `activeSessionId` matches.
 *
 * Session titles come from `chatSessionDisplayTitle` — prefer the server-side
 * `title` (set by future features), then the first 60 chars of the first
 * user message, then "Untitled chat".
 *
 * Empty / loading / error states each render their own inline placeholder so
 * the sidebar shell (header + button) is always visible.
 */

import Link from "next/link";
import { Loader2, MessageSquare, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
	chatSessionDisplayTitle,
	type ChatSessionRead,
} from "@/lib/api/chat";

export function SessionSidebar({
	sessions,
	activeSessionId,
	loading,
	error,
	creating,
	deletingId,
	onNewChat,
	onDelete,
}: {
	sessions: ChatSessionRead[] | undefined;
	activeSessionId?: string;
	loading: boolean;
	error: Error | null;
	creating: boolean;
	deletingId: string | null;
	onNewChat: () => void;
	onDelete: (session: ChatSessionRead) => void;
}) {
	return (
		<aside className="flex h-full w-full flex-col border-r border-border bg-card/40 sm:w-72">
			<div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
				<div className="flex items-center gap-2 text-xs uppercase tracking-widest text-muted-foreground">
					<MessageSquare className="h-3.5 w-3.5" />
					Chats
				</div>
				<Button
					size="sm"
					onClick={onNewChat}
					disabled={creating}
					aria-label="New chat"
				>
					{creating ? (
						<Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
					) : (
						<Plus className="mr-1.5 h-3.5 w-3.5" />
					)}
					New
				</Button>
			</div>

			<div className="flex-1 overflow-y-auto px-2 py-2">
				{loading ? (
					<div className="space-y-2 px-1 py-1">
						<Skeleton className="h-9 w-full" />
						<Skeleton className="h-9 w-full" />
						<Skeleton className="h-9 w-4/5" />
					</div>
				) : error ? (
					<p className="px-2 py-4 text-xs text-destructive">
						Could not load sessions: {error.message}
					</p>
				) : !sessions || sessions.length === 0 ? (
					<p className="px-2 py-4 text-xs text-muted-foreground">
						No chats yet. Start a new one to begin.
					</p>
				) : (
					<ul className="space-y-1">
						{sessions.map((s) => (
							<li key={s.id}>
								<SidebarRow
									session={s}
									isActive={s.id === activeSessionId}
									isDeleting={deletingId === s.id}
									onDelete={() => onDelete(s)}
								/>
							</li>
						))}
					</ul>
				)}
			</div>
		</aside>
	);
}

function SidebarRow({
	session,
	isActive,
	isDeleting,
	onDelete,
}: {
	session: ChatSessionRead;
	isActive: boolean;
	isDeleting: boolean;
	onDelete: () => void;
}) {
	const title = chatSessionDisplayTitle(session);
	return (
		<div
			className={cn(
				"group flex items-center gap-1 rounded-md pr-1 transition-colors",
				isActive ? "bg-accent" : "hover:bg-accent/60",
			)}
		>
			<Link
				href={`/chat/${session.id}`}
				className={cn(
					"flex min-w-0 flex-1 items-center gap-2 rounded-md px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring",
					isActive ? "text-foreground" : "text-muted-foreground",
				)}
			>
				<MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-70" />
				<span className="min-w-0 flex-1 truncate">{title}</span>
			</Link>
			<Button
				variant="ghost"
				size="icon"
				className="h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
				onClick={onDelete}
				disabled={isDeleting}
				aria-label={`Delete ${title}`}
			>
				{isDeleting ? (
					<Loader2 className="h-3.5 w-3.5 animate-spin" />
				) : (
					<Trash2 className="h-3.5 w-3.5" />
				)}
			</Button>
		</div>
	);
}
