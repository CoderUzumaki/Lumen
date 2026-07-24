"use client";

import { Suspense } from "react";
import Link from "next/link";
import { Loader2, Newspaper } from "lucide-react";

export const dynamic = "force-dynamic";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { FeedRow } from "@/components/news/feed-row";
import { useNewsFeed } from "@/lib/api/news";
import { useListPortfolios } from "@/lib/api/portfolios";

export default function NewsPage() {
	return (
		<Suspense fallback={<PageSkeleton />}>
			<AuthGuard>
				<NewsInner />
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

function NewsInner() {
	const feed = useNewsFeed();
	const portfolios = useListPortfolios();

	if (feed.isLoading || portfolios.isLoading) {
		return (
			<main className="flex min-h-screen items-center justify-center">
				<div className="flex items-center gap-3 text-muted-foreground">
					<Loader2 className="h-5 w-5 animate-spin" />
					Loading news feed...
				</div>
			</main>
		);
	}

	if (feed.error) {
		return (
			<main className="mx-auto max-w-3xl px-6 py-10">
				<Card>
					<CardHeader>
						<CardTitle>Could not load news</CardTitle>
						<CardDescription>{feed.error.message}</CardDescription>
					</CardHeader>
				</Card>
			</main>
		);
	}

	const activePortfolio = portfolios.data?.find((p) => p.is_active);
	const items = feed.data ?? [];

	return (
		<main className="mx-auto max-w-4xl px-6 py-10">
			<div className="mb-8 flex items-start justify-between gap-4">
				<div>
					<p className="text-xs uppercase tracking-widest text-muted-foreground">
						<span className="inline-flex items-center gap-1.5">
							<Newspaper className="h-3.5 w-3.5" />
							News feed
						</span>
					</p>
					<h1 className="mt-2 text-3xl font-semibold tracking-tight">
						Relevant to your portfolio
					</h1>
					<p className="mt-2 text-sm text-muted-foreground">
						Feed for:{" "}
						{activePortfolio ? (
							<span className="text-foreground">{activePortfolio.name}</span>
						) : (
							<span className="italic">no active portfolio</span>
						)}
						. Sorted by relevance, most recent first.
					</p>
				</div>
			</div>

			{items.length === 0 ? (
				<EmptyState hasActivePortfolio={Boolean(activePortfolio)} />
			) : (
				<div className="space-y-3">
					{items.map((item) => (
						<FeedRow key={item.cluster.id} item={item} />
					))}
				</div>
			)}
		</main>
	);
}

function EmptyState({ hasActivePortfolio }: { hasActivePortfolio: boolean }) {
	if (!hasActivePortfolio) {
		return (
			<Card>
				<CardHeader>
					<CardTitle>No active portfolio</CardTitle>
					<CardDescription>
						News is scored against the portfolio you have marked active. Set
						one active to start seeing relevant clusters here.
					</CardDescription>
				</CardHeader>
				<CardContent>
					<Button asChild variant="outline">
						<Link href="/portfolios">Go to portfolios</Link>
					</Button>
				</CardContent>
			</Card>
		);
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle>No relevant news yet</CardTitle>
				<CardDescription>
					Check back after the next ingest run — the pipeline scans news
					sources continuously and scores each cluster against your active
					portfolio.
				</CardDescription>
			</CardHeader>
		</Card>
	);
}
