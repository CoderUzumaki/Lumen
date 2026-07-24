"use client";

import { Suspense, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus, Trash2, Wand2 } from "lucide-react";

// Auth-guarded page; no static prerender. AuthGuard uses useSearchParams
// internally, so it must live under a Suspense boundary (Next 15 rule).
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	SAMPLE_PORTFOLIO_TICKERS,
	useAddPosition,
	useCreatePortfolio,
	type AssetType,
	type PositionCreateInput,
} from "@/lib/api/portfolios";

/**
 * Onboarding step 1: create the caller's first portfolio.
 *
 * A single form. The "Load sample portfolio" button seeds AAPL, MSFT, NVDA,
 * GOOGL, VOO, BND so a recruiter can skip data entry. Otherwise the user adds
 * rows manually. On submit: create the portfolio, then add every position
 * sequentially, then redirect to /briefing (a later module will render it —
 * for now the redirect target is a placeholder that stays valid).
 */
export default function OnboardingPortfolioPage() {
	return (
		<Suspense fallback={<PageSkeleton />}>
			<AuthGuard>
				<OnboardingInner />
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

type Row = PositionCreateInput & { key: string };

function newRow(overrides: Partial<PositionCreateInput> = {}): Row {
	return {
		key: crypto.randomUUID(),
		ticker: "",
		asset_type: "equity",
		currency: "USD",
		exchange: null,
		...overrides,
	};
}

function OnboardingInner() {
	const router = useRouter();
	const [name, setName] = useState("Main");
	const [rows, setRows] = useState<Row[]>([newRow()]);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const createPortfolio = useCreatePortfolio();
	const addPosition = useAddPosition();

	function setRow(index: number, patch: Partial<Row>) {
		setRows((prev) => {
			const next = [...prev];
			next[index] = { ...next[index], ...patch };
			return next;
		});
	}

	function addRow() {
		setRows((prev) => [...prev, newRow()]);
	}

	function removeRow(key: string) {
		setRows((prev) => (prev.length > 1 ? prev.filter((r) => r.key !== key) : prev));
	}

	function loadSample() {
		setRows(SAMPLE_PORTFOLIO_TICKERS.map((t) => newRow(t)));
	}

	async function handleSubmit(event: React.FormEvent) {
		event.preventDefault();
		setError(null);

		const clean = rows
			.map((r) => ({ ...r, ticker: r.ticker.trim().toUpperCase() }))
			.filter((r) => r.ticker.length > 0);

		if (clean.length === 0) {
			setError("Add at least one position (or click 'Load sample').");
			return;
		}
		if (!name.trim()) {
			setError("Give your portfolio a name.");
			return;
		}

		setSubmitting(true);
		try {
			const portfolio = await createPortfolio.mutateAsync({
				name: name.trim(),
				is_active: true,
			});
			// Sequential adds keep the FastAPI backend responses in order and
			// make error handling straightforward — the endpoint is fast.
			for (const row of clean) {
				const { key: _key, ...input } = row;
				await addPosition.mutateAsync({
					portfolioId: portfolio.id,
					input,
				});
			}
			// /briefing is BRIEF-05's territory; until then, land on the portfolios
			// list so the user sees what they just created.
			router.replace("/portfolios");
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setSubmitting(false);
		}
	}

	return (
		<main className="mx-auto max-w-3xl px-6 py-10">
			<div className="mb-8">
				<p className="text-xs uppercase tracking-widest text-muted-foreground">
					Onboarding · Step 1 of 2
				</p>
				<h1 className="mt-2 text-3xl font-semibold tracking-tight">
					Set up your portfolio
				</h1>
				<p className="mt-2 text-muted-foreground">
					Add the tickers you hold. Quantities and cost basis are optional —
					you can fill them in later.
				</p>
			</div>

			<Card>
				<CardHeader>
					<CardTitle>Portfolio</CardTitle>
					<CardDescription>
						Give it a name, then add positions. Or use the sample portfolio to
						skip data entry.
					</CardDescription>
				</CardHeader>
				<CardContent>
					<form className="space-y-6" onSubmit={handleSubmit}>
						<div className="space-y-2">
							<Label htmlFor="portfolio-name">Name</Label>
							<Input
								id="portfolio-name"
								value={name}
								onChange={(e) => setName(e.target.value)}
								placeholder="Main"
								maxLength={120}
								required
							/>
						</div>

						<div className="flex items-center justify-between">
							<div>
								<h2 className="text-sm font-medium">Positions</h2>
								<p className="text-xs text-muted-foreground">
									{rows.length} row{rows.length === 1 ? "" : "s"}
								</p>
							</div>
							<Button
								type="button"
								variant="secondary"
								onClick={loadSample}
								data-testid="load-sample"
							>
								<Wand2 className="mr-2 h-4 w-4" />
								Load sample portfolio
							</Button>
						</div>

						<div className="space-y-3">
							{rows.map((row, i) => (
								<div
									key={row.key}
									className="grid grid-cols-12 items-end gap-2 rounded-md border border-border p-3"
								>
									<div className="col-span-3 space-y-1">
										<Label className="text-xs" htmlFor={`ticker-${row.key}`}>
											Ticker
										</Label>
										<Input
											id={`ticker-${row.key}`}
											value={row.ticker}
											onChange={(e) => setRow(i, { ticker: e.target.value })}
											placeholder="AAPL"
											className="uppercase"
											maxLength={20}
											data-testid={`ticker-input-${i}`}
										/>
									</div>
									<div className="col-span-3 space-y-1">
										<Label className="text-xs" htmlFor={`type-${row.key}`}>
											Type
										</Label>
										<select
											id={`type-${row.key}`}
											value={row.asset_type ?? "equity"}
											onChange={(e) =>
												setRow(i, { asset_type: e.target.value as AssetType })
											}
											className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm"
										>
											<option value="equity">Equity</option>
											<option value="etf">ETF</option>
											<option value="crypto">Crypto</option>
											<option value="bond">Bond</option>
											<option value="other">Other</option>
										</select>
									</div>
									<div className="col-span-2 space-y-1">
										<Label className="text-xs" htmlFor={`qty-${row.key}`}>
											Qty
										</Label>
										<Input
											id={`qty-${row.key}`}
											inputMode="decimal"
											value={row.quantity ?? ""}
											onChange={(e) =>
												setRow(i, { quantity: e.target.value || null })
											}
											placeholder="—"
										/>
									</div>
									<div className="col-span-2 space-y-1">
										<Label className="text-xs" htmlFor={`ccy-${row.key}`}>
											Currency
										</Label>
										<Input
											id={`ccy-${row.key}`}
											value={row.currency ?? "USD"}
											onChange={(e) =>
												setRow(i, {
													currency: e.target.value.toUpperCase(),
												})
											}
											maxLength={3}
											className="uppercase"
										/>
									</div>
									<div className="col-span-2 space-y-1">
										<Label className="text-xs" htmlFor={`exch-${row.key}`}>
											Exchange
										</Label>
										<Input
											id={`exch-${row.key}`}
											value={row.exchange ?? ""}
											onChange={(e) =>
												setRow(i, { exchange: e.target.value || null })
											}
											placeholder="NASDAQ"
											maxLength={32}
										/>
									</div>
									<Button
										type="button"
										variant="ghost"
										size="icon"
										className="col-span-12 justify-self-end sm:col-span-12"
										onClick={() => removeRow(row.key)}
										disabled={rows.length === 1}
										aria-label={`Remove row ${i + 1}`}
									>
										<Trash2 className="h-4 w-4" />
									</Button>
								</div>
							))}
						</div>

						<Button type="button" variant="outline" onClick={addRow}>
							<Plus className="mr-2 h-4 w-4" />
							Add row
						</Button>

						{error ? (
							<p className="text-sm text-destructive" role="alert">
								{error}
							</p>
						) : null}

						<div className="flex items-center justify-end gap-3">
							<Button
								type="submit"
								disabled={submitting}
								data-testid="submit-onboarding"
							>
								{submitting ? (
									<>
										<Loader2 className="mr-2 h-4 w-4 animate-spin" />
										Saving...
									</>
								) : (
									"Continue"
								)}
							</Button>
						</div>
					</form>
				</CardContent>
			</Card>
		</main>
	);
}
