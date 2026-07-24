"use client";

import { Suspense, use, useState } from "react";
import Link from "next/link";

export const dynamic = "force-dynamic";
import {
	ArrowLeft,
	CheckCircle2,
	Loader2,
	Pencil,
	Plus,
	Trash2,
	X,
} from "lucide-react";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	useAddPosition,
	useDeletePosition,
	usePortfolio,
	useUpdatePosition,
	type Position,
	type PositionCreateInput,
	type PositionUpdateInput,
} from "@/lib/api/portfolios";

export default function PortfolioDetailPage({
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
	const query = usePortfolio(id);
	const addPosition = useAddPosition();

	const [newRow, setNewRow] = useState<PositionCreateInput>({
		ticker: "",
		asset_type: "equity",
		currency: "USD",
	});

	if (query.isLoading || !query.data) {
		return (
			<main className="flex min-h-screen items-center justify-center">
				<div className="flex items-center gap-3 text-muted-foreground">
					<Loader2 className="h-5 w-5 animate-spin" />
					Loading portfolio...
				</div>
			</main>
		);
	}

	if (query.error) {
		return (
			<main className="mx-auto max-w-3xl px-6 py-10">
				<Card>
					<CardHeader>
						<CardTitle>Could not load portfolio</CardTitle>
						<CardDescription>{query.error.message}</CardDescription>
					</CardHeader>
					<CardContent>
						<Button asChild variant="outline">
							<Link href="/portfolios">
								<ArrowLeft className="mr-2 h-4 w-4" />
								Back
							</Link>
						</Button>
					</CardContent>
				</Card>
			</main>
		);
	}

	const portfolio = query.data;
	const positions = portfolio.positions ?? [];

	async function handleAdd(event: React.FormEvent) {
		event.preventDefault();
		const ticker = newRow.ticker.trim().toUpperCase();
		if (!ticker) return;
		await addPosition.mutateAsync({
			portfolioId: id,
			input: { ...newRow, ticker },
		});
		setNewRow({ ticker: "", asset_type: "equity", currency: "USD" });
	}

	return (
		<main className="mx-auto max-w-5xl px-6 py-10">
			<div className="mb-6">
				<Button asChild variant="ghost" size="sm">
					<Link href="/portfolios">
						<ArrowLeft className="mr-2 h-4 w-4" />
						All portfolios
					</Link>
				</Button>
			</div>

			<div className="mb-8 flex items-start justify-between gap-4">
				<div>
					<h1 className="text-3xl font-semibold tracking-tight">
						{portfolio.name}
					</h1>
					<p className="mt-2 text-muted-foreground">
						{positions.length} position{positions.length === 1 ? "" : "s"}
					</p>
				</div>
				{portfolio.is_active ? (
					<Badge className="gap-1">
						<CheckCircle2 className="h-3 w-3" />
						Active portfolio
					</Badge>
				) : null}
			</div>

			<Card>
				<CardHeader>
					<CardTitle>Positions</CardTitle>
					<CardDescription>
						Click a row to edit inline. Add a new position below.
					</CardDescription>
				</CardHeader>
				<CardContent>
					{positions.length === 0 ? (
						<p className="text-sm text-muted-foreground">
							No positions yet — add one below.
						</p>
					) : (
						<div className="overflow-hidden rounded-md border border-border">
							<table className="w-full text-sm">
								<thead className="bg-muted/50 text-xs uppercase tracking-widest text-muted-foreground">
									<tr>
										<th className="px-3 py-2 text-left font-medium">Ticker</th>
										<th className="px-3 py-2 text-left font-medium">Type</th>
										<th className="px-3 py-2 text-right font-medium">Qty</th>
										<th className="px-3 py-2 text-left font-medium">Currency</th>
										<th className="px-3 py-2 text-left font-medium">
											Exchange
										</th>
										<th className="px-3 py-2 text-right font-medium">Actions</th>
									</tr>
								</thead>
								<tbody>
									{positions.map((p) => (
										<PositionRow key={p.id} position={p} />
									))}
								</tbody>
							</table>
						</div>
					)}

					<form
						onSubmit={handleAdd}
						className="mt-6 grid grid-cols-12 items-end gap-2 rounded-md border border-dashed border-border p-3"
					>
						<div className="col-span-3 space-y-1">
							<Label className="text-xs" htmlFor="new-ticker">
								Ticker
							</Label>
							<Input
								id="new-ticker"
								value={newRow.ticker}
								onChange={(e) =>
									setNewRow((r) => ({ ...r, ticker: e.target.value }))
								}
								placeholder="AAPL"
								className="uppercase"
								maxLength={20}
							/>
						</div>
						<div className="col-span-3 space-y-1">
							<Label className="text-xs" htmlFor="new-type">
								Type
							</Label>
							<select
								id="new-type"
								value={newRow.asset_type ?? "equity"}
								onChange={(e) =>
									setNewRow((r) => ({
										...r,
										asset_type: e.target.value as PositionCreateInput["asset_type"],
									}))
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
							<Label className="text-xs" htmlFor="new-qty">
								Qty
							</Label>
							<Input
								id="new-qty"
								inputMode="decimal"
								value={newRow.quantity ?? ""}
								onChange={(e) =>
									setNewRow((r) => ({ ...r, quantity: e.target.value || null }))
								}
								placeholder="—"
							/>
						</div>
						<div className="col-span-2 space-y-1">
							<Label className="text-xs" htmlFor="new-ccy">
								Currency
							</Label>
							<Input
								id="new-ccy"
								value={newRow.currency ?? "USD"}
								onChange={(e) =>
									setNewRow((r) => ({
										...r,
										currency: e.target.value.toUpperCase(),
									}))
								}
								maxLength={3}
								className="uppercase"
							/>
						</div>
						<div className="col-span-2 flex justify-end">
							<Button type="submit" disabled={addPosition.isPending}>
								{addPosition.isPending ? (
									<Loader2 className="mr-2 h-4 w-4 animate-spin" />
								) : (
									<Plus className="mr-2 h-4 w-4" />
								)}
								Add
							</Button>
						</div>
					</form>
				</CardContent>
			</Card>
		</main>
	);
}

function PositionRow({ position }: { position: Position }) {
	const [editing, setEditing] = useState(false);
	const [draft, setDraft] = useState<PositionUpdateInput>(position);
	const update = useUpdatePosition();
	const del = useDeletePosition();

	async function save() {
		await update.mutateAsync({ positionId: position.id, input: draft });
		setEditing(false);
	}

	function cancel() {
		setDraft(position);
		setEditing(false);
	}

	if (!editing) {
		return (
			<tr className="border-t border-border">
				<td className="px-3 py-2 font-mono font-medium">{position.ticker}</td>
				<td className="px-3 py-2 text-muted-foreground">
					{position.asset_type}
				</td>
				<td className="px-3 py-2 text-right font-mono">
					{position.quantity ?? "—"}
				</td>
				<td className="px-3 py-2">{position.currency}</td>
				<td className="px-3 py-2 text-muted-foreground">
					{position.exchange ?? "—"}
				</td>
				<td className="px-3 py-2 text-right">
					<Button
						variant="ghost"
						size="icon"
						onClick={() => setEditing(true)}
						aria-label={`Edit ${position.ticker}`}
					>
						<Pencil className="h-4 w-4" />
					</Button>
					<Button
						variant="ghost"
						size="icon"
						onClick={() => {
							if (confirm(`Delete ${position.ticker}?`)) {
								del.mutate(position.id);
							}
						}}
						disabled={del.isPending}
						aria-label={`Delete ${position.ticker}`}
					>
						<Trash2 className="h-4 w-4" />
					</Button>
				</td>
			</tr>
		);
	}

	return (
		<tr className="border-t border-border bg-accent/30">
			<td className="px-3 py-2">
				<Input
					value={draft.ticker ?? ""}
					onChange={(e) => setDraft({ ...draft, ticker: e.target.value })}
					className="h-8 uppercase"
					maxLength={20}
				/>
			</td>
			<td className="px-3 py-2">
				<select
					value={draft.asset_type ?? "equity"}
					onChange={(e) =>
						setDraft({
							...draft,
							asset_type: e.target.value as PositionUpdateInput["asset_type"],
						})
					}
					className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
				>
					<option value="equity">equity</option>
					<option value="etf">etf</option>
					<option value="crypto">crypto</option>
					<option value="bond">bond</option>
					<option value="other">other</option>
				</select>
			</td>
			<td className="px-3 py-2 text-right">
				<Input
					value={draft.quantity ?? ""}
					onChange={(e) =>
						setDraft({ ...draft, quantity: e.target.value || null })
					}
					className="h-8 text-right"
					inputMode="decimal"
				/>
			</td>
			<td className="px-3 py-2">
				<Input
					value={draft.currency ?? "USD"}
					onChange={(e) =>
						setDraft({ ...draft, currency: e.target.value.toUpperCase() })
					}
					className="h-8 uppercase"
					maxLength={3}
				/>
			</td>
			<td className="px-3 py-2">
				<Input
					value={draft.exchange ?? ""}
					onChange={(e) =>
						setDraft({ ...draft, exchange: e.target.value || null })
					}
					className="h-8"
					maxLength={32}
				/>
			</td>
			<td className="px-3 py-2 text-right">
				<Button
					variant="ghost"
					size="icon"
					onClick={save}
					disabled={update.isPending}
					aria-label="Save changes"
				>
					{update.isPending ? (
						<Loader2 className="h-4 w-4 animate-spin" />
					) : (
						<CheckCircle2 className="h-4 w-4" />
					)}
				</Button>
				<Button
					variant="ghost"
					size="icon"
					onClick={cancel}
					aria-label="Cancel edit"
				>
					<X className="h-4 w-4" />
				</Button>
			</td>
		</tr>
	);
}
