"use client";

/**
 * `/chat/[id]` — full chat view for one session.
 *
 * Layout mirrors `/chat`: sidebar on the left (same component, active row
 * highlighted), messages + composer on the right.
 *
 * Streaming lifecycle for a send:
 *
 *   1. On submit, we append two client-only bubbles: the user echo (marked
 *      as `pending: false`, id `local-user-<n>`) and an assistant placeholder
 *      (`pending: true`, id `local-assistant-<n>`). Both use client-local
 *      IDs so React keeps them stable across the swap to server truth.
 *   2. `useSse` opens `POST /api/chat/sessions/{id}/messages` with the user
 *      content in the body. The parser JSON-decodes `data` for each frame
 *      and dispatches by `event`.
 *   3. `token`     — flip placeholder's `pending` off and replace content
 *                    with `delta` (CHAT-04 sends one synthetic frame with
 *                    the full assembled content; see backend docstring).
 *   4. `citations` — attach the array to the placeholder assistant.
 *   5. `done`      — mark stream complete, refetch the session so the
 *                    placeholder rows are replaced by the server-side rows
 *                    with real UUIDs + created_at.
 *   6. `error`     — flip placeholder to error state with the message + a
 *                    retry button that re-sends the same content.
 *   7. `tool_call` / `tool_result` — CHAT-04 does NOT emit these today.
 *                    We accept + ignore them so a future CHAT-03 refactor
 *                    doesn't break the client. Console-logged for
 *                    debuggability.
 *
 * Suspense + AuthGuard + `dynamic = "force-dynamic"` mirror the pattern in
 * `app/portfolios/[id]/page.tsx`. Params are unwrapped with `use()` per Next
 * 15's async-params contract.
 */

import {
	Suspense,
	use,
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertTriangle, ArrowLeft, Loader2 } from "lucide-react";

export const dynamic = "force-dynamic";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ChatComposer } from "@/components/chat/chat-composer";
import { MessageList } from "@/components/chat/message-list";
import { type BubbleMessage } from "@/components/chat/message-bubble";
import { SessionSidebar } from "@/components/chat/session-sidebar";
import {
	Alert,
	AlertDescription,
	AlertTitle,
} from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { useSse } from "@/hooks/use-sse";
import {
	chatKeys,
	chatSessionDisplayTitle,
	useChatSession,
	useCreateChatSession,
	useDeleteChatSession,
	useListChatSessions,
	type ChatMessageRead,
	type ChatSessionRead,
} from "@/lib/api/chat";
import type { Citation } from "@/lib/api/impact";
import type { SseEvent } from "@/lib/api/client";
import { useQueryClient } from "@tanstack/react-query";

// ---------------------------------------------------------------------------
// SSE frame types (mirror `_chat_sse_generator` in backend/app/routes/chat.py)
// ---------------------------------------------------------------------------

type TokenFrame = { event: "token"; data: { delta: string } };
type CitationsFrame = { event: "citations"; data: Citation[] };
type DoneFrame = { event: "done"; data: { message_id: string } };
type ErrorFrame = { event: "error"; data: { message: string } };
// Wire-contract-reserved but not emitted today — parsed + ignored below.
type ToolCallFrame = {
	event: "tool_call";
	data: { name?: string; args?: unknown };
};
type ToolResultFrame = {
	event: "tool_result";
	data: { name?: string; result?: unknown };
};

type ChatSseFrame =
	| TokenFrame
	| CitationsFrame
	| DoneFrame
	| ErrorFrame
	| ToolCallFrame
	| ToolResultFrame
	| { event: string; data: unknown };

function parseChatFrame(raw: SseEvent): ChatSseFrame | null {
	try {
		const data = JSON.parse(raw.data);
		return { event: raw.event, data } as ChatSseFrame;
	} catch {
		// Non-JSON payload (shouldn't happen from CHAT-04, but be defensive) —
		// return with the raw string so the switch below can still dispatch.
		return { event: raw.event, data: raw.data };
	}
}

// ---------------------------------------------------------------------------
// Page shell
// ---------------------------------------------------------------------------

export default function ChatSessionPage({
	params,
}: {
	// Next 15: dynamic route params come wrapped in a Promise. Unwrap with `use`.
	params: Promise<{ id: string }>;
}) {
	const { id } = use(params);
	return (
		<Suspense fallback={<PageSkeleton />}>
			<AuthGuard>
				<SessionInner id={id} />
			</AuthGuard>
		</Suspense>
	);
}

function PageSkeleton() {
	return (
		<main className="flex min-h-screen items-center justify-center">
			<Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
		</main>
	);
}

// ---------------------------------------------------------------------------
// Inner page
// ---------------------------------------------------------------------------

function SessionInner({ id }: { id: string }) {
	const router = useRouter();
	const qc = useQueryClient();

	const sessions = useListChatSessions();
	const session = useChatSession(id);
	const createSession = useCreateChatSession();
	const deleteSession = useDeleteChatSession();

	const [deletingId, setDeletingId] = useState<string | null>(null);

	// Composer state.
	const [draft, setDraft] = useState("");

	// Client-only bubbles overlaid on top of the persisted history. Cleared
	// on each `done` frame after the session refetch lands.
	const [localMessages, setLocalMessages] = useState<BubbleMessage[]>([]);

	// The content we're currently streaming a reply for — kept so `Retry`
	// on an errored assistant bubble knows what to resend.
	const [pendingContent, setPendingContent] = useState<string | null>(null);

	// Track the client-local ids for the in-flight pair so SSE callbacks can
	// mutate the assistant placeholder without a stale closure.
	const activeIdsRef = useRef<{ user: string; assistant: string } | null>(
		null,
	);

	// Force-remount `useSse` between sends by bumping a key. `useSse.start()`
	// aborts any prior stream but we also want the parser closure to close
	// over the fresh `activeIdsRef` — a fresh mount is the simplest path.
	const [sendCounter, setSendCounter] = useState(0);

	// Update an assistant placeholder in-place. Falls through cleanly if the
	// message id is no longer in `localMessages` (e.g. the session refetched
	// and swept it away).
	const updateLocal = useCallback(
		(messageId: string, patch: Partial<BubbleMessage>) => {
			setLocalMessages((prev) =>
				prev.map((m) => (m.id === messageId ? { ...m, ...patch } : m)),
			);
		},
		[],
	);

	// SSE — mounted lazily via `start()` inside `handleSubmit`. Note the
	// `sendCounter` in `path`: mutating it forces a fresh useSse instance
	// each turn without leaving stale closures behind.
	const sse = useSse<ChatSseFrame>({
		path: `/api/chat/sessions/${id}/messages?_=${sendCounter}`,
		method: "POST",
		body: pendingContent === null ? undefined : { content: pendingContent },
		enabled: false,
		parse: parseChatFrame,
		onEvent: (evt) => {
			const ids = activeIdsRef.current;
			if (!ids) return;
			switch (evt.event) {
				case "token": {
					const delta = (evt.data as TokenFrame["data"])?.delta ?? "";
					updateLocal(ids.assistant, {
						pending: false,
						content: delta,
					});
					break;
				}
				case "citations": {
					const citations = Array.isArray(evt.data)
						? (evt.data as Citation[])
						: [];
					updateLocal(ids.assistant, { citations });
					break;
				}
				case "done": {
					// Refetch the session so client-local rows get replaced by the
					// server-persisted ones (real UUIDs + created_at). The
					// message-list keeps rendering the local rows until the fetch
					// resolves, then we drop them.
					qc.invalidateQueries({ queryKey: chatKeys.session(id) });
					qc.invalidateQueries({ queryKey: chatKeys.sessions() });
					session
						.refetch()
						.then(() => {
							setLocalMessages([]);
							setPendingContent(null);
							activeIdsRef.current = null;
						})
						.catch(() => {
							// Even if the refetch fails, drop the pending content so
							// the composer isn't wedged. The error will bubble via
							// `session.error`.
							setPendingContent(null);
							activeIdsRef.current = null;
						});
					break;
				}
				case "error": {
					const message =
						(evt.data as ErrorFrame["data"])?.message ??
						"Chat turn failed";
					updateLocal(ids.assistant, {
						pending: false,
						error: true,
						errorMessage: message,
					});
					break;
				}
				case "tool_call":
				case "tool_result": {
					// CHAT-04 does not emit these today. Accept + ignore for
					// forward-compat with the future CHAT-03 refactor.
					console.debug("chat SSE (ignored):", evt.event, evt.data);
					break;
				}
				default:
					// Unknown event — log for debuggability; don't render.
					console.debug("chat SSE (unknown event):", evt.event, evt.data);
					break;
			}
		},
	});

	// If `useSse` reports a transport-level error (e.g. 500 on POST), flip the
	// assistant placeholder to error state so the user has a retry path.
	useEffect(() => {
		if (!sse.error) return;
		const ids = activeIdsRef.current;
		if (!ids) return;
		updateLocal(ids.assistant, {
			pending: false,
			error: true,
			errorMessage: sse.error,
		});
	}, [sse.error, updateLocal]);

	// Combine persisted history + client-only bubbles for the message list.
	const messages: BubbleMessage[] = useMemo(() => {
		const persisted: BubbleMessage[] = (session.data?.messages ?? []).map(
			(m: ChatMessageRead) => ({ ...m }),
		);
		return [...persisted, ...localMessages];
	}, [session.data?.messages, localMessages]);

	function handleSubmit() {
		const content = draft.trim();
		if (!content) return;
		if (sse.connected) return;

		const nonce = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
		const userId = `local-user-${nonce}`;
		const assistantId = `local-assistant-${nonce}`;
		activeIdsRef.current = { user: userId, assistant: assistantId };

		const nowIso = new Date().toISOString();
		const userBubble: BubbleMessage = {
			id: userId,
			session_id: id,
			role: "user",
			content,
			citations: [],
			tokens_used: null,
			langsmith_run_id: null,
			guardrail_violations: [],
			created_at: nowIso,
		};
		const assistantBubble: BubbleMessage = {
			id: assistantId,
			session_id: id,
			role: "assistant",
			content: "",
			citations: [],
			tokens_used: null,
			langsmith_run_id: null,
			guardrail_violations: [],
			created_at: nowIso,
			pending: true,
		};
		setLocalMessages((prev) => [...prev, userBubble, assistantBubble]);
		setDraft("");
		setPendingContent(content);
		setSendCounter((n) => n + 1);
	}

	// `pendingContent` + `sendCounter` update in the same synchronous batch as
	// `setPendingContent`, but `useSse`'s `body` closure only re-computes on
	// re-render — so we start after commit. `start()` reads the fresh body via
	// its useCallback dep on `body`.
	useEffect(() => {
		if (pendingContent === null) return;
		if (sse.connected) return;
		// Only start if we haven't already streamed for this counter. `done`
		// clears pendingContent, so a second useEffect fire for the same
		// counter won't re-run start.
		sse.start();
		// Intentionally exclude `sse` (it's stable enough via keys) so we don't
		// double-start on every re-render.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [pendingContent, sendCounter]);

	function handleRetry() {
		const ids = activeIdsRef.current;
		if (!ids || !pendingContent) return;
		// Reset the assistant placeholder back to `pending` and re-open the
		// stream with the same content.
		updateLocal(ids.assistant, {
			pending: true,
			error: false,
			errorMessage: undefined,
			content: "",
			citations: [],
		});
		setSendCounter((n) => n + 1);
	}

	function handleNewChat() {
		createSession.mutate(undefined, {
			onSuccess: (s) => router.push(`/chat/${s.id}`),
		});
	}

	function handleDelete(target: ChatSessionRead) {
		const title = target.title?.trim() || "this chat";
		if (!confirm(`Delete "${title}"? This can't be undone.`)) return;
		setDeletingId(target.id);
		deleteSession.mutate(target.id, {
			onSettled: () => setDeletingId(null),
			onSuccess: () => {
				// If we deleted the session we're currently viewing, bounce back
				// to /chat.
				if (target.id === id) {
					router.replace("/chat");
				}
			},
		});
	}

	// -----------------------------------------------------------------------
	// Render branches
	// -----------------------------------------------------------------------

	const sidebar = (
		<SessionSidebar
			sessions={sessions.data}
			activeSessionId={id}
			loading={sessions.isLoading}
			error={sessions.error as Error | null}
			creating={createSession.isPending}
			deletingId={deletingId}
			onNewChat={handleNewChat}
			onDelete={handleDelete}
		/>
	);

	// Session loading (first fetch — subsequent refetches during streaming
	// don't hit this branch because `session.data` is already populated).
	if (session.isLoading && !session.data) {
		return (
			<PageShell sidebar={sidebar}>
				<div className="flex flex-1 items-center justify-center">
					<div className="flex items-center gap-3 text-muted-foreground">
						<Loader2 className="h-5 w-5 animate-spin" />
						Loading chat…
					</div>
				</div>
			</PageShell>
		);
	}

	// 404 (not caller's session, or gone) — folded into a "not found" card.
	if (session.error) {
		const is404 = session.error.message.includes("404");
		return (
			<PageShell sidebar={sidebar}>
				<div className="flex flex-1 items-center justify-center p-6">
					<Card className="w-full max-w-md">
						<CardHeader>
							<CardTitle>
								{is404 ? "Chat not found" : "Could not load chat"}
							</CardTitle>
							<CardDescription>
								{is404
									? "This chat doesn't exist or belongs to another account."
									: session.error.message}
							</CardDescription>
						</CardHeader>
						<CardContent>
							<Button asChild variant="outline">
								<Link href="/chat">
									<ArrowLeft className="mr-2 h-4 w-4" />
									Back to chats
								</Link>
							</Button>
						</CardContent>
					</Card>
				</div>
			</PageShell>
		);
	}

	const active = session.data;
	const title = active
		? chatSessionDisplayTitle(active)
		: "Chat";

	return (
		<PageShell sidebar={sidebar}>
			<div className="flex flex-1 flex-col overflow-hidden">
				<header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-6">
					<div className="min-w-0">
						<p className="text-xs uppercase tracking-widest text-muted-foreground">
							Chat
						</p>
						<h1 className="mt-0.5 truncate text-lg font-medium">
							{title}
						</h1>
					</div>
				</header>

				<div className="flex-1 overflow-y-auto">
					{messages.length === 0 ? (
						<EmptyThread />
					) : (
						<MessageList messages={messages} onRetry={handleRetry} />
					)}
				</div>

				{sse.error && !activeIdsRef.current ? (
					<div className="border-t border-border bg-background/95 px-4 pt-3 sm:px-6">
						<Alert variant="destructive">
							<AlertTriangle className="h-4 w-4" />
							<AlertTitle>Connection error</AlertTitle>
							<AlertDescription>{sse.error}</AlertDescription>
						</Alert>
					</div>
				) : null}

				<ChatComposer
					value={draft}
					onChange={setDraft}
					onSubmit={handleSubmit}
					disabled={sse.connected}
					sending={sse.connected}
				/>
			</div>
		</PageShell>
	);
}

function PageShell({
	sidebar,
	children,
}: {
	sidebar: React.ReactNode;
	children: React.ReactNode;
}) {
	return (
		<main className="flex h-screen flex-col overflow-hidden">
			<div className="flex flex-1 overflow-hidden">
				{sidebar}
				<section className="flex flex-1 flex-col overflow-hidden">
					{children}
				</section>
			</div>
		</main>
	);
}

function EmptyThread() {
	return (
		<div className="flex h-full items-center justify-center p-8">
			<div className="max-w-md text-center">
				<h2 className="text-lg font-medium">Say hello</h2>
				<p className="mt-2 text-sm text-muted-foreground">
					Ask about a position, a news cluster, or run a hypothetical. Lumen
					replies with citations.
				</p>
			</div>
		</div>
	);
}
