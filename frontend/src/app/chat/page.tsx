"use client";

/**
 * `/chat` — the chat index page. Two behaviors:
 *
 *   1. Deep-link seed. `/chat?seed=<cluster_id>` creates a new session with
 *      `seed_cluster_id` set, then replaces the URL with `/chat/<new id>`.
 *      We track the last seed we've acted on in a ref so re-renders don't
 *      loop-create sessions on the same param.
 *
 *   2. Empty right pane. Without a seed param, we show the sidebar + a large
 *      "Start a chat — pick a session or start a new one" placeholder. If the
 *      caller has zero sessions we swap that for a stronger "Start your first
 *      chat" CTA.
 *
 * Suspense + AuthGuard + `dynamic = "force-dynamic"` mirror the pattern in
 * `app/portfolios/page.tsx` — required so Next 15 doesn't try to prerender a
 * subtree that reads `useSearchParams()` inside `AuthGuard`.
 */

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, MessageSquare, Plus, Sparkles } from "lucide-react";

export const dynamic = "force-dynamic";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SessionSidebar } from "@/components/chat/session-sidebar";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	useCreateChatSession,
	useDeleteChatSession,
	useListChatSessions,
	type ChatSessionRead,
} from "@/lib/api/chat";

export default function ChatIndexPage() {
	return (
		<Suspense fallback={<PageSkeleton />}>
			<AuthGuard>
				<ChatIndexInner />
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

function ChatIndexInner() {
	const router = useRouter();
	const searchParams = useSearchParams();
	const seedClusterId = searchParams.get("seed");

	const sessions = useListChatSessions();
	const createSession = useCreateChatSession();
	const deleteSession = useDeleteChatSession();

	const [deletingId, setDeletingId] = useState<string | null>(null);
	const [seedError, setSeedError] = useState<string | null>(null);

	// Track the seed we've already acted on so re-renders (e.g. after the
	// list refetches) don't loop-create sessions on the same param.
	const consumedSeedRef = useRef<string | null>(null);

	// Deep-link seed: create a session with `seed_cluster_id`, then redirect
	// to `/chat/<new id>`. Fires at most once per param value.
	useEffect(() => {
		if (!seedClusterId) return;
		if (consumedSeedRef.current === seedClusterId) return;
		if (createSession.isPending) return;
		consumedSeedRef.current = seedClusterId;
		setSeedError(null);
		createSession.mutate(
			{ seed_cluster_id: seedClusterId },
			{
				onSuccess: (session) => {
					router.replace(`/chat/${session.id}`);
				},
				onError: (err) => {
					setSeedError(
						err instanceof Error ? err.message : String(err),
					);
					// Allow the user to retry manually via the "New chat" button
					// by clearing the consumed marker on error.
					consumedSeedRef.current = null;
				},
			},
		);
	}, [seedClusterId, createSession, router]);

	function handleNewChat() {
		createSession.mutate(undefined, {
			onSuccess: (session) => {
				router.push(`/chat/${session.id}`);
			},
		});
	}

	function handleDelete(session: ChatSessionRead) {
		const title = session.title?.trim() || "this chat";
		if (!confirm(`Delete "${title}"? This can't be undone.`)) return;
		setDeletingId(session.id);
		deleteSession.mutate(session.id, {
			onSettled: () => setDeletingId(null),
		});
	}

	const hasSessions = (sessions.data?.length ?? 0) > 0;
	const seeding = Boolean(seedClusterId) && createSession.isPending;

	return (
		<main className="flex h-screen flex-col overflow-hidden">
			<div className="flex flex-1 overflow-hidden">
				<SessionSidebar
					sessions={sessions.data}
					loading={sessions.isLoading}
					error={sessions.error as Error | null}
					creating={createSession.isPending}
					deletingId={deletingId}
					onNewChat={handleNewChat}
					onDelete={handleDelete}
				/>

				<section className="flex flex-1 flex-col overflow-hidden">
					<div className="flex flex-1 items-center justify-center overflow-y-auto p-6">
						{seeding ? (
							<div className="flex items-center gap-3 text-muted-foreground">
								<Loader2 className="h-5 w-5 animate-spin" />
								Starting a chat about the selected cluster…
							</div>
						) : seedError ? (
							<SeedErrorCard message={seedError} onRetry={handleNewChat} />
						) : hasSessions ? (
							<EmptyPickCta />
						) : (
							<FirstChatCta
								onStart={handleNewChat}
								creating={createSession.isPending}
							/>
						)}
					</div>
				</section>
			</div>
		</main>
	);
}

function EmptyPickCta() {
	return (
		<div className="max-w-md text-center">
			<div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-border bg-card">
				<MessageSquare className="h-5 w-5 text-muted-foreground" />
			</div>
			<h2 className="mt-4 text-lg font-medium">Start a chat</h2>
			<p className="mt-2 text-sm text-muted-foreground">
				Pick a session on the left or start a new one to chat about your
				portfolio, a cluster, or a specific ticker.
			</p>
		</div>
	);
}

function FirstChatCta({
	onStart,
	creating,
}: {
	onStart: () => void;
	creating: boolean;
}) {
	return (
		<Card className="w-full max-w-md">
			<CardHeader className="items-center text-center">
				<Sparkles className="h-8 w-8 text-muted-foreground" />
				<CardTitle className="mt-2 text-xl">Start your first chat</CardTitle>
				<CardDescription className="max-w-xs">
					Ask Lumen anything about your portfolio, a specific position, or a
					news cluster you&apos;re watching. Answers arrive with citations.
				</CardDescription>
			</CardHeader>
			<CardContent className="flex justify-center">
				<Button size="lg" onClick={onStart} disabled={creating}>
					{creating ? (
						<>
							<Loader2 className="mr-2 h-4 w-4 animate-spin" />
							Creating…
						</>
					) : (
						<>
							<Plus className="mr-2 h-4 w-4" />
							Start your first chat
						</>
					)}
				</Button>
			</CardContent>
		</Card>
	);
}

function SeedErrorCard({
	message,
	onRetry,
}: {
	message: string;
	onRetry: () => void;
}) {
	return (
		<Card className="w-full max-w-md">
			<CardHeader>
				<CardTitle>Could not start a seeded chat</CardTitle>
				<CardDescription>{message}</CardDescription>
			</CardHeader>
			<CardContent>
				<Button onClick={onRetry}>
					<Plus className="mr-2 h-4 w-4" />
					Start a chat anyway
				</Button>
			</CardContent>
		</Card>
	);
}
