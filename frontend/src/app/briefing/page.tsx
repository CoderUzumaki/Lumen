"use client";

/**
 * `/briefing` — the daily briefing page.
 *
 * Data flow:
 *   1. On mount, `useLatestBriefing` fetches the caller's most recent
 *      briefing. A 404 is folded into `data === null` so we can render an
 *      empty-state without treating it as an error.
 *   2. "Regenerate" fires a POST → the mutation resolves 202 immediately.
 *      We then poll `useLatestBriefing` at ~1Hz for up to 15s, stopping as
 *      soon as the `briefing_date` advances past the pre-regen date.
 *   3. "Generate live" opens the SSE stream via `useSse` (Bearer-aware). The
 *      hook flips `done: true` on `complete` / `error`. `partial_content`
 *      frames carry a full `BriefingContent` payload (despite the "partial"
 *      name), which we swap into `liveContent` and render in place of the
 *      cached briefing.
 *
 * Suspense + AuthGuard + `dynamic = "force-dynamic"` mirror the pattern in
 * `app/portfolios/page.tsx` — required so Next 15 doesn't try to prerender
 * a subtree that reads `useSearchParams()` inside `AuthGuard`.
 */

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
	AlertTriangle,
	Eye,
	Loader2,
	RefreshCw,
	Sparkles,
	TrendingUp,
} from "lucide-react";

export const dynamic = "force-dynamic";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BriefingItemCard } from "@/components/briefing/briefing-item-card";
import {
	StreamStatus,
	type StreamStatusKind,
} from "@/components/briefing/stream-status";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useListPortfolios } from "@/lib/api/portfolios";
import {
	useLatestBriefing,
	useRegenerateBriefing,
	type BriefingContent,
	type BriefingRead,
} from "@/lib/api/briefings";
import { useSse } from "@/hooks/use-sse";
import type { SseEvent } from "@/lib/api/client";

export default function BriefingPage() {
	return (
		<Suspense fallback={<PageSkeleton />}>
			<AuthGuard>
				<BriefingInner />
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
// SSE frame types
// ---------------------------------------------------------------------------

type NodeStarted = { event: "node_started"; data: { node: string } };
type NodeCompleted = {
	event: "node_completed";
	data: { node: string; duration_ms: number };
};
type PartialContent = { event: "partial_content"; data: BriefingContent };
type StreamComplete = { event: "complete"; data: { briefing_id: string } };
type StreamError = { event: "error"; data: { message: string } };

type BriefingSseEvent =
	| NodeStarted
	| NodeCompleted
	| PartialContent
	| StreamComplete
	| StreamError
	| { event: string; data: unknown };

function parseBriefingFrame(raw: SseEvent): BriefingSseEvent | null {
	try {
		const data = JSON.parse(raw.data);
		return { event: raw.event, data } as BriefingSseEvent;
	} catch {
		return { event: raw.event, data: raw.data };
	}
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function BriefingInner() {
	// Latest briefing (server truth).
	const latest = useLatestBriefing();

	// Live-generated content displaces server truth when set.
	const [liveContent, setLiveContent] = useState<BriefingContent | null>(null);
	const [status, setStatus] = useState<StreamStatusKind>({ kind: "idle" });

	// Track the pre-regen briefing_date so we know when the poll succeeded.
	const preRegenDateRef = useRef<string | null>(null);
	const [polling, setPolling] = useState(false);

	// Active portfolio for the header badge.
	const portfolios = useListPortfolios();
	const activePortfolio = useMemo(
		() => portfolios.data?.find((p) => p.is_active) ?? null,
		[portfolios.data],
	);

	const regen = useRegenerateBriefing();

	// SSE stream.
	const sse = useSse<BriefingSseEvent>({
		path: "/api/briefings/stream",
		method: "GET",
		enabled: false,
		parse: parseBriefingFrame,
		onEvent: (evt) => {
			switch (evt.event) {
				case "node_started": {
					const node = (evt.data as NodeStarted["data"])?.node ?? "";
					setStatus({ kind: "running", label: `${node} starting…` });
					break;
				}
				case "node_completed": {
					const d = evt.data as NodeCompleted["data"];
					setStatus({
						kind: "running",
						label: `${d?.node ?? "step"} done in ${d?.duration_ms ?? 0}ms`,
					});
					break;
				}
				case "partial_content": {
					const content = evt.data as BriefingContent;
					setLiveContent(content);
					break;
				}
				case "complete": {
					setStatus({ kind: "done", label: "briefing generated" });
					// Refetch server truth so a page refresh shows the persisted row.
					latest.refetch();
					break;
				}
				case "error": {
					const msg =
						(evt.data as StreamError["data"])?.message ?? "Unknown error";
					setStatus({ kind: "error", message: `Could not generate: ${msg}` });
					break;
				}
				default:
					break;
			}
		},
	});

	// Regenerate → poll until `briefing_date` advances or 15s elapse.
	useEffect(() => {
		if (!polling) return;
		const preDate = preRegenDateRef.current;
		const startedAt = Date.now();
		const interval = window.setInterval(async () => {
			if (Date.now() - startedAt > 15_000) {
				window.clearInterval(interval);
				setPolling(false);
				setStatus({
					kind: "error",
					message: "Regenerate timed out after 15s.",
				});
				return;
			}
			try {
				const result = await latest.refetch();
				const newDate = result.data?.briefing_date ?? null;
				if (newDate && newDate !== preDate) {
					window.clearInterval(interval);
					setPolling(false);
					setStatus({ kind: "done", label: "briefing regenerated" });
				}
			} catch {
				// Keep polling — a transient error shouldn't abort the loop.
			}
		}, 1000);
		return () => window.clearInterval(interval);
	}, [polling, latest]);

	const handleRegenerate = async () => {
		preRegenDateRef.current = latest.data?.briefing_date ?? null;
		setLiveContent(null);
		setStatus({ kind: "connecting" });
		try {
			await regen.mutateAsync();
			setStatus({ kind: "running", label: "regenerating…" });
			setPolling(true);
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			setStatus({ kind: "error", message });
		}
	};

	const handleGenerateLive = () => {
		setLiveContent(null);
		setStatus({ kind: "connecting" });
		sse.start();
	};

	// Loading state.
	if (latest.isLoading) {
		return (
			<main className="flex min-h-screen items-center justify-center">
				<div className="flex items-center gap-3 text-muted-foreground">
					<Loader2 className="h-5 w-5 animate-spin" />
					Loading your briefing…
				</div>
			</main>
		);
	}

	// Real error (not a 404 — that's folded into data === null).
	if (latest.error) {
		return (
			<main className="mx-auto max-w-3xl px-6 py-10">
				<Card>
					<CardHeader>
						<CardTitle>Could not load briefing</CardTitle>
						<CardDescription>{latest.error.message}</CardDescription>
					</CardHeader>
				</Card>
			</main>
		);
	}

	const briefing: BriefingRead | null = latest.data ?? null;
	const isBusy = sse.connected || polling;
	// Render precedence: live SSE content (in-flight) > cached briefing.
	const content: BriefingContent | null =
		liveContent ?? briefing?.structured_content ?? null;

	// Empty state — 404 → prompt user to generate one.
	if (!briefing && !liveContent) {
		return (
			<main className="mx-auto max-w-3xl px-6 py-10">
				<Header
					portfolioName={activePortfolio?.name ?? null}
					briefingDate={null}
					onRegenerate={handleRegenerate}
					onGenerateLive={handleGenerateLive}
					regenerating={regen.isPending || polling}
					streaming={sse.connected}
					showRegen={false}
				/>
				<StreamStatus status={status} />
				<Card className="mt-6">
					<CardHeader className="items-center text-center">
						<Sparkles className="h-8 w-8 text-muted-foreground" />
						<CardTitle className="mt-2 text-xl">No briefing yet</CardTitle>
						<CardDescription className="max-w-md">
							Lumen hasn&apos;t generated a briefing for you yet. Generate one
							now — you&apos;ll see the synthesizer&apos;s progress stream in
							live.
						</CardDescription>
					</CardHeader>
					<CardContent className="flex justify-center">
						<Button
							size="lg"
							onClick={handleGenerateLive}
							disabled={isBusy}
						>
							{sse.connected ? (
								<>
									<Loader2 className="mr-2 h-4 w-4 animate-spin" />
									Generating…
								</>
							) : (
								<>
									<Sparkles className="mr-2 h-4 w-4" />
									Generate now
								</>
							)}
						</Button>
					</CardContent>
				</Card>
				{status.kind === "error" ? (
					<div className="mt-4 flex justify-center">
						<Button variant="outline" onClick={handleGenerateLive}>
							<RefreshCw className="mr-2 h-4 w-4" />
							Retry
						</Button>
					</div>
				) : null}
			</main>
		);
	}

	return (
		<main className="mx-auto max-w-5xl px-6 py-10">
			<Header
				portfolioName={activePortfolio?.name ?? null}
				briefingDate={briefing?.briefing_date ?? null}
				onRegenerate={handleRegenerate}
				onGenerateLive={handleGenerateLive}
				regenerating={regen.isPending || polling}
				streaming={sse.connected}
				showRegen={!!briefing}
			/>

			<div className="mb-6 flex flex-wrap items-center gap-2">
				<StreamStatus status={status} />
				{liveContent ? (
					<Badge variant="secondary" className="gap-1 text-xs">
						<Sparkles className="h-3 w-3" />
						Live preview (not yet persisted)
					</Badge>
				) : null}
			</div>

			{content ? (
				<div className="space-y-10">
					<Section
						icon={<TrendingUp className="h-4 w-4" />}
						label="Top movers for you"
						empty="No top movers today."
					>
						{content.top_movers.length > 0 ? (
							<div className="grid gap-4 sm:grid-cols-2">
								{content.top_movers.map((item) => (
									<BriefingItemCard key={item.impact_id} item={item} />
								))}
							</div>
						) : null}
					</Section>

					<Separator />

					<Section
						icon={<Eye className="h-4 w-4" />}
						label="Watchlist for tomorrow"
						empty="Nothing on the watchlist."
					>
						{content.watchlist.length > 0 ? (
							<div className="grid gap-4 sm:grid-cols-2">
								{content.watchlist.map((item) => (
									<BriefingItemCard key={item.impact_id} item={item} />
								))}
							</div>
						) : null}
					</Section>

					<Separator />

					<Section
						icon={<AlertTriangle className="h-4 w-4" />}
						label="What would change my thinking"
						empty="No falsifiability checks recorded."
					>
						{content.what_would_change_my_thinking.length > 0 ? (
							<Card>
								<CardContent className="pt-6">
									<ul className="space-y-3">
										{content.what_would_change_my_thinking.map((s, i) => (
											<li
												key={`${i}-${s.slice(0, 24)}`}
												className="flex gap-3 text-sm leading-relaxed"
											>
												<span
													className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
													aria-hidden
												/>
												<span>{s}</span>
											</li>
										))}
									</ul>
								</CardContent>
							</Card>
						) : null}
					</Section>

					{content.generated_summary ? (
						<>
							<Separator />
							<section>
								<p className="text-xs uppercase tracking-widest text-muted-foreground">
									Summary
								</p>
								<p className="mt-3 text-sm leading-relaxed text-muted-foreground">
									{content.generated_summary}
								</p>
							</section>
						</>
					) : null}
				</div>
			) : null}

			{status.kind === "error" ? (
				<Alert variant="destructive" className="mt-8">
					<AlertTriangle className="h-4 w-4" />
					<AlertTitle>Generation failed</AlertTitle>
					<AlertDescription>
						<p>{status.message}</p>
						<Button
							variant="outline"
							size="sm"
							className="mt-3"
							onClick={handleGenerateLive}
						>
							<RefreshCw className="mr-2 h-4 w-4" />
							Retry
						</Button>
					</AlertDescription>
				</Alert>
			) : null}
		</main>
	);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Header({
	portfolioName,
	briefingDate,
	onRegenerate,
	onGenerateLive,
	regenerating,
	streaming,
	showRegen,
}: {
	portfolioName: string | null;
	briefingDate: string | null;
	onRegenerate: () => void;
	onGenerateLive: () => void;
	regenerating: boolean;
	streaming: boolean;
	showRegen: boolean;
}) {
	return (
		<div className="mb-8 flex flex-wrap items-start justify-between gap-4">
			<div>
				<p className="text-xs uppercase tracking-widest text-muted-foreground">
					Daily briefing
				</p>
				<h1 className="mt-2 text-3xl font-semibold tracking-tight">
					{briefingDate ? formatDate(briefingDate) : "Today"}
				</h1>
				<div className="mt-3 flex flex-wrap items-center gap-2">
					{portfolioName ? (
						<Badge variant="outline" className="gap-1.5">
							<span className="h-1.5 w-1.5 rounded-full bg-primary" />
							{portfolioName}
						</Badge>
					) : null}
					{briefingDate ? (
						<Badge variant="secondary" className="font-mono text-xs">
							{briefingDate}
						</Badge>
					) : null}
				</div>
			</div>
			<div className="flex flex-wrap items-center gap-2">
				{showRegen ? (
					<Button
						variant="outline"
						onClick={onRegenerate}
						disabled={regenerating || streaming}
					>
						{regenerating ? (
							<>
								<Loader2 className="mr-2 h-4 w-4 animate-spin" />
								Regenerating…
							</>
						) : (
							<>
								<RefreshCw className="mr-2 h-4 w-4" />
								Regenerate
							</>
						)}
					</Button>
				) : null}
				<Button
					onClick={onGenerateLive}
					disabled={streaming || regenerating}
				>
					{streaming ? (
						<>
							<Loader2 className="mr-2 h-4 w-4 animate-spin" />
							Streaming…
						</>
					) : (
						<>
							<Sparkles className="mr-2 h-4 w-4" />
							Generate live
						</>
					)}
				</Button>
			</div>
		</div>
	);
}

function Section({
	icon,
	label,
	empty,
	children,
}: {
	icon: React.ReactNode;
	label: string;
	empty: string;
	children: React.ReactNode;
}) {
	// If `children` is falsy / empty, we still want to render a graceful
	// placeholder rather than an empty section.
	const hasContent =
		children !== null && children !== undefined && children !== false;
	return (
		<section>
			<div className="mb-4 flex items-center gap-2 text-xs uppercase tracking-widest text-muted-foreground">
				{icon}
				<span>{label}</span>
			</div>
			{hasContent ? (
				children
			) : (
				<p className="text-sm text-muted-foreground">{empty}</p>
			)}
		</section>
	);
}

function formatDate(iso: string): string {
	// iso is YYYY-MM-DD. Parse as local to avoid a UTC shift.
	const [y, m, d] = iso.split("-").map((n) => Number.parseInt(n, 10));
	if (!y || !m || !d) return iso;
	const date = new Date(y, m - 1, d);
	return date.toLocaleDateString(undefined, {
		weekday: "long",
		month: "long",
		day: "numeric",
		year: "numeric",
	});
}
