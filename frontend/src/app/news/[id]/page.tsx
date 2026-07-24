"use client";

import { Suspense, use } from "react";
import Link from "next/link";
import { ArrowLeft, Info, Loader2 } from "lucide-react";

export const dynamic = "force-dynamic";

import { AuthGuard } from "@/components/auth/auth-guard";
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
import { Skeleton } from "@/components/ui/skeleton";
import { ImpactCard } from "@/components/impact/impact-card";
import { ScoreBar } from "@/components/news/score-bar";
import { SourceChip, dedupeSources } from "@/components/news/source-chip";
import {
	formatRelativeTime,
	useClusterDetail,
	type NewsClusterRead,
} from "@/lib/api/news";
import {
	POLL_TIMEOUT_MS,
	useClusterImpact,
	useRegenerateImpact,
} from "@/lib/api/impact";

export default function NewsDetailPage({
	params,
}: {
	// Next 15: dynamic route params come wrapped in a Promise. Unwrap with `use`.
	params: Promise<{ id: string }>;
}) {
	const { id } = use(params);
	return (
		<Suspense fallback={<PageSkeleton />}>
			<AuthGuard>
				<DetailInner id={id} />
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

function DetailInner({ id }: { id: string }) {
	const detail = useClusterDetail(id);
	const impact = useClusterImpact(id);
	const regenerate = useRegenerateImpact({
		onSuccess: () => {
			// The polling loop in `useClusterImpact` picks up the new 202 flow on
			// its next tick, but we nudge it now so the UI flips instantly.
			impact.resetPoll();
			impact.refetch();
		},
	});

	if (detail.isLoading || !detail.data) {
		return (
			<main className="mx-auto max-w-4xl px-6 py-10">
				<BackLink />
				<Card>
					<CardContent className="py-10">
						<div className="flex items-center gap-3 text-muted-foreground">
							<Loader2 className="h-5 w-5 animate-spin" />
							Loading cluster...
						</div>
					</CardContent>
				</Card>
			</main>
		);
	}

	if (detail.error) {
		return (
			<main className="mx-auto max-w-4xl px-6 py-10">
				<BackLink />
				<Card>
					<CardHeader>
						<CardTitle>Could not load this cluster</CardTitle>
						<CardDescription>{detail.error.message}</CardDescription>
					</CardHeader>
				</Card>
			</main>
		);
	}

	const { cluster, relevance } = detail.data;

	return (
		<main className="mx-auto max-w-4xl px-6 py-10">
			<BackLink />
			<ClusterHeader cluster={cluster} score={relevance?.score ?? null} />
			<div className="mt-8">
				<ImpactSection
					clusterId={id}
					state={impact.data}
					isLoading={impact.isLoading}
					isPollTimedOut={impact.isPollTimedOut}
					error={impact.error}
					onRefetch={() => {
						impact.resetPoll();
						impact.refetch();
					}}
					onRegenerate={() => regenerate.mutate(id)}
					isRegenerating={regenerate.isPending}
				/>
			</div>
		</main>
	);
}

function BackLink() {
	return (
		<div className="mb-6">
			<Button asChild variant="ghost" size="sm">
				<Link href="/news">
					<ArrowLeft className="mr-2 h-4 w-4" />
					All news
				</Link>
			</Button>
		</div>
	);
}

function ClusterHeader({
	cluster,
	score,
}: {
	cluster: NewsClusterRead;
	score: string | null;
}) {
	const sources = dedupeSources(cluster.items ?? []);
	return (
		<div>
			<h1 className="text-3xl font-semibold tracking-tight leading-tight">
				{cluster.canonical_title}
			</h1>
			{cluster.canonical_summary ? (
				<p className="mt-3 text-base leading-relaxed text-muted-foreground">
					{cluster.canonical_summary}
				</p>
			) : null}

			<div className="mt-4 flex flex-wrap items-center gap-1.5">
				{cluster.entity_tickers.map((ticker) => (
					<Badge
						key={ticker}
						variant="outline"
						className="font-mono text-[11px] uppercase"
					>
						{ticker}
					</Badge>
				))}
			</div>

			<div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
				{sources.map((s) => (
					<SourceChip key={s} source={s} />
				))}
				<span>Last seen {formatRelativeTime(cluster.last_seen_at)}</span>
			</div>

			{score !== null ? (
				<div className="mt-6 max-w-md">
					<ScoreBar score={score} label="Portfolio relevance" />
				</div>
			) : null}
		</div>
	);
}

function ImpactSection({
	clusterId,
	state,
	isLoading,
	isPollTimedOut,
	error,
	onRefetch,
	onRegenerate,
	isRegenerating,
}: {
	clusterId: string;
	state: ReturnType<typeof useClusterImpact>["data"];
	isLoading: boolean;
	isPollTimedOut: boolean;
	error: Error | null;
	onRefetch: () => void;
	onRegenerate: () => void;
	isRegenerating: boolean;
}) {
	if (error) {
		return (
			<Card>
				<CardHeader>
					<CardTitle>Impact assessment failed</CardTitle>
					<CardDescription>{error.message}</CardDescription>
				</CardHeader>
				<CardContent>
					<Button variant="outline" size="sm" onClick={onRefetch}>
						Try again
					</Button>
				</CardContent>
			</Card>
		);
	}

	if (isLoading || !state) {
		return <GeneratingCard status="loading" />;
	}

	if (state.status === "not_found") {
		return (
			<Card>
				<CardHeader>
					<CardTitle>No impact assessment</CardTitle>
					<CardDescription>{state.detail}</CardDescription>
				</CardHeader>
				<CardContent className="text-sm text-muted-foreground">
					<p>
						Lumen only generates impact assessments for clusters that score
						above the relevance threshold and belong to your active
						portfolio. If you just activated a different portfolio, try
						refreshing.
					</p>
				</CardContent>
			</Card>
		);
	}

	if (state.status === "generating") {
		return (
			<GeneratingCard
				status={isPollTimedOut ? "timeout" : "polling"}
				onRefetch={onRefetch}
			/>
		);
	}

	// state.status === "cached"
	return (
		<Card>
			<CardContent className="p-6">
				<ImpactCard
					impact={state.impact}
					onRegenerate={onRegenerate}
					isRegenerating={isRegenerating}
				/>
			</CardContent>
			{/* Silence unused-var lint about `clusterId` — it's part of the API to
			    keep the section self-contained if we later split callbacks. */}
			<span data-cluster-id={clusterId} hidden />
		</Card>
	);
}

function GeneratingCard({
	status,
	onRefetch,
}: {
	status: "loading" | "polling" | "timeout";
	onRefetch?: () => void;
}) {
	if (status === "timeout") {
		return (
			<Card>
				<CardHeader>
					<CardTitle>Still generating</CardTitle>
					<CardDescription>
						This impact assessment is taking longer than{" "}
						{Math.round(POLL_TIMEOUT_MS / 1000)}s to build. Refresh in a bit —
						the pipeline will land it in the background.
					</CardDescription>
				</CardHeader>
				<CardContent>
					{onRefetch ? (
						<Button variant="outline" size="sm" onClick={onRefetch}>
							Check again
						</Button>
					) : null}
				</CardContent>
			</Card>
		);
	}

	const label =
		status === "loading"
			? "Loading impact assessment..."
			: "Generating your impact assessment...";

	return (
		<Card>
			<CardContent className="space-y-6 p-6">
				<div className="flex items-center gap-3 text-sm text-muted-foreground">
					<Loader2 className="h-4 w-4 animate-spin" />
					{label}
				</div>
				<Alert>
					<Info className="h-4 w-4" />
					<AlertTitle>What&apos;s happening</AlertTitle>
					<AlertDescription>
						Lumen is reasoning over the news cluster, retrieving comparable
						historical events, and drafting a citation-backed mechanism +
						magnitude estimate. This usually takes 10–30 seconds.
					</AlertDescription>
				</Alert>
				<div className="space-y-3">
					<Skeleton className="h-4 w-40" />
					<Skeleton className="h-24 w-full" />
					<Skeleton className="h-3 w-full" />
					<Skeleton className="h-3 w-11/12" />
					<Skeleton className="h-3 w-9/12" />
				</div>
			</CardContent>
		</Card>
	);
}
