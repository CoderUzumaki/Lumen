"use client";

/**
 * Typed API client + TanStack Query hooks for /api/chat.
 *
 * Wire contract mirrors `backend/app/schemas/chat.py` + `backend/app/routes/chat.py`.
 * The `Citation` shape is imported from `@/lib/api/impact` — the backend
 * re-exports the same class so a single source of truth defines it for both
 * chat and impact.
 *
 * The SSE side of the endpoint (`POST /api/chat/sessions/{id}/messages`) is
 * consumed via `useSse` from `@/hooks/use-sse` inside the chat page — this
 * file covers only the JSON endpoints.
 *
 * Note on CHAT-04 SSE frames (see the backend route docstring):
 *   The graph today is single-await, so the server emits one synthetic `token`
 *   frame carrying the full assembled assistant content, then `citations`,
 *   then `done`. `tool_call` / `tool_result` frames are wire-contract-reserved
 *   for a future refactor and are NOT emitted today; the chat page's parser
 *   accepts + ignores them so a future refactor doesn't break clients.
 */

import {
	useMutation,
	useQuery,
	useQueryClient,
	type UseMutationOptions,
} from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import type { Citation } from "@/lib/api/impact";

// ---------------------------------------------------------------------------
// Types — mirror `backend/app/schemas/chat.py`.
// ---------------------------------------------------------------------------

export type ChatRole = "user" | "assistant" | "system";

export type ChatMessageRead = {
	id: string;
	session_id: string;
	role: ChatRole;
	content: string;
	citations: Citation[];
	tokens_used: number | null;
	langsmith_run_id: string | null;
	guardrail_violations: Array<Record<string, unknown>>;
	created_at: string; // ISO 8601
};

export type ChatSessionRead = {
	id: string;
	user_id: string;
	portfolio_id: string;
	title: string | null;
	seed_cluster_id: string | null;
	created_at: string;
	updated_at: string;
	messages: ChatMessageRead[];
};

export type ChatSessionCreateInput = {
	title?: string;
	seed_cluster_id?: string;
};

export type ChatMessageInput = { content: string };

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const chatKeys = {
	all: ["chat"] as const,
	sessions: () => [...chatKeys.all, "sessions"] as const,
	session: (id: string) => [...chatKeys.all, "session", id] as const,
};

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

/**
 * List every chat session for the caller. Backend returns newest-first and
 * omits `messages` on list responses (always `[]`).
 */
export function useListChatSessions(options?: { enabled?: boolean }) {
	return useQuery<ChatSessionRead[]>({
		queryKey: chatKeys.sessions(),
		queryFn: () => apiFetch<ChatSessionRead[]>("/api/chat/sessions"),
		enabled: options?.enabled,
	});
}

/**
 * Fetch one session with its full message history in chronological order.
 * Backend returns 404 if the session isn't owned by the caller.
 */
export function useChatSession(id: string | undefined) {
	return useQuery<ChatSessionRead>({
		queryKey: id ? chatKeys.session(id) : [...chatKeys.all, "session", "__missing__"],
		queryFn: () => apiFetch<ChatSessionRead>(`/api/chat/sessions/${id!}`),
		enabled: Boolean(id),
	});
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/**
 * Create a new chat session. Backend picks the caller's active portfolio and
 * returns the session with `messages: []`. A 400 comes back if
 * `seed_cluster_id` was passed but doesn't exist; 404 if the caller has no
 * active portfolio.
 */
export function useCreateChatSession(
	options?: UseMutationOptions<ChatSessionRead, Error, ChatSessionCreateInput | void>,
) {
	const qc = useQueryClient();
	return useMutation({
		mutationFn: (input: ChatSessionCreateInput | void) =>
			apiFetch<ChatSessionRead>("/api/chat/sessions", {
				method: "POST",
				body: JSON.stringify(input ?? {}),
			}),
		onSuccess: (...args) => {
			qc.invalidateQueries({ queryKey: chatKeys.sessions() });
			// Forward all args (data, variables, context, ...) so callers with
			// their own onSuccess handler get the full v5-style tuple.
			(options?.onSuccess as ((...a: unknown[]) => unknown) | undefined)?.(
				...args,
			);
		},
		...options,
	});
}

/**
 * Delete a session. Backend returns 204 on success or 404 for cross-user
 * sessions (existence never leaks).
 */
export function useDeleteChatSession(
	options?: UseMutationOptions<void, Error, string>,
) {
	const qc = useQueryClient();
	return useMutation({
		mutationFn: (id: string) =>
			apiFetch<void>(`/api/chat/sessions/${id}`, {
				method: "DELETE",
				parseJson: false,
			}),
		onSuccess: (...args) => {
			qc.invalidateQueries({ queryKey: chatKeys.sessions() });
			// Also drop the individual session cache entry — passing `id` as the
			// second arg to onSuccess in v5 gives us the deleted id here.
			const deletedId = args[1] as string | undefined;
			if (deletedId) {
				qc.removeQueries({ queryKey: chatKeys.session(deletedId) });
			}
			(options?.onSuccess as ((...a: unknown[]) => unknown) | undefined)?.(
				...args,
			);
		},
		...options,
	});
}

// ---------------------------------------------------------------------------
// Presentation helpers
// ---------------------------------------------------------------------------

/**
 * Session-list display title: prefer the server-side `title` (set by future
 * features), then the first 60 chars of the first user message if any, then
 * "Untitled chat".
 */
export function chatSessionDisplayTitle(session: ChatSessionRead): string {
	if (session.title && session.title.trim()) {
		return session.title.trim();
	}
	const firstUser = session.messages?.find((m) => m.role === "user");
	if (firstUser?.content) {
		const trimmed = firstUser.content.trim();
		if (trimmed) {
			return trimmed.length > 60 ? `${trimmed.slice(0, 60)}…` : trimmed;
		}
	}
	return "Untitled chat";
}
