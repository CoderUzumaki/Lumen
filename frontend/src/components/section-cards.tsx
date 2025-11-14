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
			try {
				const user = tokenManager.getUser();
				if (!user?.id) {
					// Fallback to localStorage if no user
					const storedInvoices = localStorage.getItem("invoices");
					const invoicesData = storedInvoices
						? JSON.parse(storedInvoices)
						: [];
					setInvoices(invoicesData);
					return;
				}

				// Fetch from API
				const response = await transactionApi.getTransactions(
					user.id as string
				);
				if (response.success && response.transactions) {
					// Map transaction data to invoice format for cards
					const mappedInvoices = response.transactions.map(
						(t: any) => ({
							id: t.id,
							status: t.status || "pending",
							amount_due: t.total_amount,
							confidence_score: t.confidence_score,
							created_at: t.created_at,
						})
					);
					setInvoices(mappedInvoices);
				}
			} catch (error) {
				console.error("Error fetching invoices:", error);
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
			console.log("📊 SectionCards: Refreshing due to invoice update");
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
			<Card className="@container/card bg-gradient-to-br from-primary/5 to-card shadow-sm">
				<CardHeader>
					<CardDescription>Total Invoices</CardDescription>
					<CardTitle className="text-3xl font-semibold tabular-nums">
						{totalInvoices}
					</CardTitle>
					<CardAction>
						<Badge variant="outline" className="bg-background/50">
							<IconTrendingUp className="w-3 h-3" />
							All time
						</Badge>
					</CardAction>
				</CardHeader>
				<CardFooter className="flex-col items-start gap-1.5 text-sm">
					<div className="line-clamp-1 flex gap-2 font-medium">
						Total invoices processed
					</div>
					<div className="text-muted-foreground">
						Invoices in your system
					</div>
				</CardFooter>
			</Card>

			{/* Approved Invoices Card */}
			<Card className="@container/card bg-gradient-to-br from-green-500/10 via-green-500/5 to-card shadow-sm border-green-500/20">
				<CardHeader>
					<CardDescription>Approved Invoices</CardDescription>
					<CardTitle className="text-3xl font-semibold tabular-nums text-green-700 dark:text-green-400">
						{approvedInvoices}
					</CardTitle>
					<CardAction>
						<Badge
							variant="outline"
							className="bg-green-500/10 border-green-500/30 text-green-700 dark:text-green-400"
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
					<div className="line-clamp-1 flex gap-2 font-medium text-green-700 dark:text-green-400">
						Ready for payment
					</div>
					<div className="text-muted-foreground">
						Verified and approved
					</div>
				</CardFooter>
			</Card>

			{/* Pending Review Card */}
			<Card className="@container/card bg-gradient-to-br from-orange-500/10 via-yellow-500/5 to-card shadow-sm border-orange-500/20">
				<CardHeader>
					<CardDescription>Needs Review</CardDescription>
					<CardTitle className="text-3xl font-semibold tabular-nums text-orange-700 dark:text-orange-400">
						{pendingInvoices}
					</CardTitle>
					<CardAction>
						<Badge
							variant="outline"
							className="bg-orange-500/10 border-orange-500/30 text-orange-700 dark:text-orange-400"
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
					<div className="line-clamp-1 flex gap-2 font-medium text-orange-700 dark:text-orange-400">
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
		<Card className="@container/card">
			<CardHeader>
				<div className="h-4 w-24 bg-muted rounded animate-pulse mb-2"></div>
				<div className="h-8 w-16 bg-muted rounded animate-pulse"></div>
			</CardHeader>
			<CardFooter className="flex-col items-start gap-1.5">
				<div className="h-4 w-32 bg-muted rounded animate-pulse"></div>
				<div className="h-3 w-40 bg-muted rounded animate-pulse"></div>
			</CardFooter>
		</Card>
	);
}
