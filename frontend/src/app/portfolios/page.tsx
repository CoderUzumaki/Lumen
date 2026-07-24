"use client";

import { Suspense, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CheckCircle2, Loader2, Plus, Trash2, ArrowRight } from "lucide-react";

export const dynamic = "force-dynamic";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	useActivatePortfolio,
	useDeletePortfolio,
	useListPortfolios,
	type Portfolio,
} from "@/lib/api/portfolios";

export default function PortfoliosPage() {
	return (
		<Suspense fallback={<PageSkeleton />}>
			<AuthGuard>
				<PortfoliosInner />
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

function PortfoliosInner() {
	const router = useRouter();
	const query = useListPortfolios();
	const activate = useActivatePortfolio();
	const del = useDeletePortfolio();

	// Onboarding redirect: a signed-in user with zero portfolios lands on the
	// onboarding form. Runs post-render so we don't block the initial paint.
	useEffect(() => {
		if (query.data && query.data.length === 0) {
			router.replace("/onboarding/portfolio");
		}
	}, [query.data, router]);

	if (query.isLoading || !query.data) {
		return (
			<main className="flex min-h-screen items-center justify-center">
				<div className="flex items-center gap-3 text-muted-foreground">
					<Loader2 className="h-5 w-5 animate-spin" />
					Loading your portfolios...
				</div>
			</main>
		);
	}

	if (query.error) {
		return (
			<main className="mx-auto max-w-3xl px-6 py-10">
				<Card>
					<CardHeader>
						<CardTitle>Could not load portfolios</CardTitle>
						<CardDescription>{query.error.message}</CardDescription>
					</CardHeader>
				</Card>
			</main>
		);
	}

	const portfolios = query.data ?? [];

	return (
		<main className="mx-auto max-w-5xl px-6 py-10">
			<div className="mb-8 flex items-center justify-between">
				<div>
					<p className="text-xs uppercase tracking-widest text-muted-foreground">
						Portfolios
					</p>
					<h1 className="mt-2 text-3xl font-semibold tracking-tight">
						Your portfolios
					</h1>
					<p className="mt-2 text-muted-foreground">
						One portfolio is active at a time. Briefings and impact analyses
						are scoped to the active portfolio.
					</p>
				</div>
				<Button asChild>
					<Link href="/onboarding/portfolio">
						<Plus className="mr-2 h-4 w-4" />
						New portfolio
					</Link>
				</Button>
			</div>

			<div className="grid gap-4 sm:grid-cols-2">
				{portfolios.map((p) => (
					<PortfolioCard
						key={p.id}
						portfolio={p}
						activating={activate.isPending}
						deleting={del.isPending}
						onActivate={() => activate.mutate(p.id)}
						onDelete={() => {
							if (confirm(`Delete "${p.name}" and all its positions?`)) {
								del.mutate(p.id);
							}
						}}
					/>
				))}
			</div>
		</main>
	);
}

function PortfolioCard({
	portfolio,
	activating,
	deleting,
	onActivate,
	onDelete,
}: {
	portfolio: Portfolio;
	activating: boolean;
	deleting: boolean;
	onActivate: () => void;
	onDelete: () => void;
}) {
	const positionCount = portfolio.positions?.length ?? 0;
	return (
		<Card>
			<CardHeader>
				<div className="flex items-start justify-between gap-2">
					<div>
						<CardTitle className="text-lg">{portfolio.name}</CardTitle>
						<CardDescription>
							{positionCount} position{positionCount === 1 ? "" : "s"}
						</CardDescription>
					</div>
					{portfolio.is_active ? (
						<Badge className="gap-1" variant="default">
							<CheckCircle2 className="h-3 w-3" />
							Active
						</Badge>
					) : null}
				</div>
			</CardHeader>
			<CardContent className="flex items-center justify-between gap-2">
				<Button asChild variant="ghost" size="sm">
					<Link href={`/portfolios/${portfolio.id}`}>
						View details
						<ArrowRight className="ml-2 h-4 w-4" />
					</Link>
				</Button>
				<div className="flex items-center gap-2">
					{!portfolio.is_active ? (
						<Button
							variant="outline"
							size="sm"
							onClick={onActivate}
							disabled={activating}
						>
							{activating ? "..." : "Set active"}
						</Button>
					) : null}
					<Button
						variant="ghost"
						size="icon"
						onClick={onDelete}
						disabled={deleting}
						aria-label={`Delete ${portfolio.name}`}
					>
						<Trash2 className="h-4 w-4" />
					</Button>
				</div>
			</CardContent>
		</Card>
	);
}
