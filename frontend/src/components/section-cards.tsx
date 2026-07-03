"use client";

import { IconTrendingUp } from "@tabler/icons-react";
import { Badge } from "@/components/ui/badge";
import {
	Card,
	CardAction,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { useEffect, useState } from "react";
import { EmailStatusCard } from "./emailStatusCard";
import { eventBus, EVENTS } from "@/lib/events";
import { transactionApi, tokenManager } from "@/lib/api/client";

import { logger } from "@/lib/logger";
interface Invoice {
	id: number;
	status: string;
	amount_due: number | null;
	confidence_score: number | null;
	created_at: string;
}

export function SectionCards() {
	const [invoices, setInvoices] = useState<Invoice[]>([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		const fetchInvoices = async () => {
			setLoading(true);
			try {
				logger.debug("📊 SectionCards: Fetching invoices from API...");

				// Always fetch from API with hardcoded user ID
				const response = await transactionApi.getTransactions({
					page: 1,
					page_size: 1000,
					sort_by: "created_at",
					sort_order: "desc",
				});
				if (response.success && response.data) {
					logger.debug(
						`📊 SectionCards: Fetched ${response.data.length} transactions`
					);
					// Map transaction data to invoice format for cards
					const mappedInvoices = response.data.map((t: any) => ({
						id: t.id,
						status: "completed",
						amount_due: t.total_amount,
						confidence_score: t.confidence_score,
						created_at: t.created_at,
					}));
					setInvoices(mappedInvoices);
				} else {
					console.warn("📊 SectionCards: No data received from API");
					setInvoices([]);
				}
			} catch (error) {
				console.error(
					"📊 SectionCards: Error fetching invoices:",
					error
				);
				// Fallback to localStorage on error
				const storedInvoices = localStorage.getItem("invoices");
				const invoicesData = storedInvoices
					? JSON.parse(storedInvoices)
					: [];
				setInvoices(invoicesData);
			} finally {
				setLoading(false);
			}
		};

		fetchInvoices();

		// Listen for invoice updates and refresh
		const unsubscribe = eventBus.on(EVENTS.INVOICE_UPDATED, () => {
			logger.debug("📊 SectionCards: Refreshing due to invoice update");
			fetchInvoices();
		});

		// Cleanup listener on unmount
		return unsubscribe;
	}, []);

	// Calculate statistics based on database status only (no confidence filtering)
	const totalInvoices = invoices.length;

	// "completed" status means ready for payment (approved)
	const approvedInvoices = invoices.filter((inv) => {
		return inv.status === "completed";
	}).length;

	// "pending", "processing", or "failed" means needs review
	const pendingInvoices = invoices.filter((inv) => {
		return (
			inv.status === "pending" ||
			inv.status === "processing" ||
			inv.status === "failed"
		);
	}).length;

	if (loading) {
		return (
			<>
				<SkeletonCard />
				<SkeletonCard />
				<SkeletonCard />
				<SkeletonCard />
			</>
		);
	}

	return (
		<>
			{/* Email Status Card */}
			<EmailStatusCard />

			{/* Total Invoices Card */}
			<Card className="@container/card border-border/70 bg-card/80 shadow-lg shadow-black/10">
				<CardHeader>
					<CardDescription>
						Total Invoices
					</CardDescription>
					<CardTitle className="text-3xl font-semibold tabular-nums">
						{totalInvoices}
					</CardTitle>
					<CardAction>
						<Badge
							variant="outline"
							className="border-border/70 bg-background/60 text-muted-foreground"
						>
							<IconTrendingUp className="w-3 h-3" />
							All time
						</Badge>
					</CardAction>
				</CardHeader>
				<CardFooter className="flex-col items-start gap-1.5 text-sm">
					<div className="line-clamp-1 flex gap-2 font-medium text-foreground">
						Total invoices processed
					</div>
					<div className="text-muted-foreground">
						Invoices in your system
					</div>
				</CardFooter>
			</Card>

			{/* Approved Invoices Card */}
			<Card className="@container/card border-primary/20 bg-primary/8 shadow-lg shadow-black/10">
				<CardHeader>
					<CardDescription>
						Approved Invoices
					</CardDescription>
					<CardTitle className="text-3xl font-semibold tabular-nums text-primary">
						{approvedInvoices}
					</CardTitle>
					<CardAction>
						<Badge
							variant="outline"
							className="border-primary/30 bg-primary/10 text-primary"
						>
							<IconTrendingUp className="w-3 h-3" />
							{totalInvoices > 0
								? Math.round(
										(approvedInvoices / totalInvoices) * 100
								  )
								: 0}
							%
						</Badge>
					</CardAction>
				</CardHeader>
				<CardFooter className="flex-col items-start gap-1.5 text-sm">
					<div className="line-clamp-1 flex gap-2 font-medium text-primary">
						Ready for payment
					</div>
					<div className="text-muted-foreground">
						Verified and approved
					</div>
				</CardFooter>
			</Card>

			{/* Pending Review Card */}
			<Card className="@container/card border-amber-500/20 bg-amber-500/8 shadow-lg shadow-black/10">
				<CardHeader>
					<CardDescription>
						Needs Review
					</CardDescription>
					<CardTitle className="text-3xl font-semibold tabular-nums text-amber-300">
						{pendingInvoices}
					</CardTitle>
					<CardAction>
						<Badge
							variant="outline"
							className="border-amber-500/30 bg-amber-500/10 text-amber-300"
						>
							<IconTrendingUp className="w-3 h-3" />
							{totalInvoices > 0
								? Math.round(
										(pendingInvoices / totalInvoices) * 100
								  )
								: 0}
							%
						</Badge>
					</CardAction>
				</CardHeader>
				<CardFooter className="flex-col items-start gap-1.5 text-sm">
					<div className="line-clamp-1 flex gap-2 font-medium text-amber-300">
						Requires attention
					</div>
					<div className="text-muted-foreground">
						Pending verification
					</div>
				</CardFooter>
			</Card>
		</>
	);
}

function SkeletonCard() {
	return (
		<Card className="@container/card border-border/70 bg-card/80">
			<CardHeader>
				<div className="mb-2 h-4 w-24 animate-pulse rounded bg-muted"></div>
				<div className="h-8 w-16 animate-pulse rounded bg-muted"></div>
			</CardHeader>
			<CardFooter className="flex-col items-start gap-1.5">
				<div className="h-4 w-32 animate-pulse rounded bg-muted"></div>
				<div className="h-3 w-40 animate-pulse rounded bg-muted"></div>
			</CardFooter>
		</Card>
	);
}
