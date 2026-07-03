"use client";

import { useEffect, useState } from "react";
import { InvoiceEditDialog } from "@/components/invoiceEditDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";
import { transactionApi } from "@/lib/api/client";
import { eventBus, EVENTS } from "@/lib/events";

import { logger } from "@/lib/logger";
interface Invoice {
	id: string; // UUID from database
	vendor_name: string | null;
	invoice_number: string | null;
	date: string | null;
	total_amount: number | null;
	tax_amount: number | null;
	payment_method: string | null;
	address: string | null;
	category: string | null;
	created_at: string;
	items?: Array<{
		item_name: string;
		quantity: number;
		unit_price: number;
		total_price: number;
	}>;
}

export default function AnimatedListItemUse() {
	const [items, setItems] = useState<Invoice[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(
		null
	);
	const [dialogOpen, setDialogOpen] = useState(false);

	const fetchInvoices = async () => {
		try {
			setLoading(true);
			setError(null);

			logger.debug(
				"🔄 AnimatedList: Fetching invoices from database API..."
			);

			// Fetch from database API
			const response = await transactionApi.getTransactions({
				page: 1,
				page_size: 1000,
				sort_by: "created_at",
				sort_order: "desc",
			});

			logger.debug("📥 AnimatedList: API Response:", {
				success: response.success,
				count: response.data?.length,
			});

			if (response.success && response.data) {
				logger.debug(
					`✅ AnimatedList: Fetched ${response.data.length} transactions from database`
				);
				setItems(response.data);
			} else {
				console.warn(
					"⚠️ AnimatedList: API returned no data or success=false"
				);
				setItems([]);
			}
		} catch (error) {
			console.error("Error fetching transactions:", error);

			// Fallback to localStorage if API fails
			try {
				const storedInvoices = localStorage.getItem("invoices");
				const invoices = storedInvoices
					? JSON.parse(storedInvoices)
					: [];
				logger.debug("Using localStorage fallback:", invoices);
				setItems(invoices);
			} catch (localError) {
				setItems([]);
			}

			const errorMessage =
				error instanceof Error
					? error.message
					: "Failed to fetch transactions";
			setError(errorMessage);
		} finally {
			setLoading(false);
		}
	};

	const handleManualRefresh = async () => {
		await fetchInvoices();
	};

	// Load invoices on component mount and listen for updates
	useEffect(() => {
		logger.debug(
			"🔄 AnimatedListItemUse: Component mounted, fetching invoices..."
		);
		fetchInvoices();

		// Listen for invoice updates
		const handleInvoiceUpdate = () => {
			logger.debug(
				"🔔 AnimatedListItemUse: Invoice update event received, refreshing..."
			);
			fetchInvoices();
		};

		const unsubscribe = eventBus.on(
			EVENTS.INVOICE_UPDATED,
			handleInvoiceUpdate
		);
		logger.debug("👂 AnimatedListItemUse: Listening for invoice updates");

		return () => {
			logger.debug("🔇 AnimatedListItemUse: Cleaning up event listener");
			unsubscribe();
		};
	}, []);

	const handleOpenDialog = (invoice: Invoice) => {
		setSelectedInvoice(invoice);
		setDialogOpen(true);
	};

	const formatCurrency = (amount: number | null) =>
		amount == null
			? "N/A"
			: new Intl.NumberFormat("en-IN", {
					style: "currency",
					currency: "INR",
					maximumFractionDigits: 0,
			  }).format(amount);

	const formatDate = (value: string | null) =>
		value
			? new Date(value).toLocaleDateString("en-IN", {
					day: "2-digit",
					month: "short",
					year: "numeric",
			  })
			: "N/A";

	if (loading) {
		return (
			<div className="flex items-center justify-center rounded-2xl border border-border/70 bg-background/50 p-8">
				<div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary"></div>
				<span className="ml-3 text-sm text-muted-foreground">
					Loading invoices...
				</span>
			</div>
		);
	}

	if (error) {
		return (
			<div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-8 text-center">
				<p className="mb-4 text-sm text-destructive">{error}</p>
				<Button onClick={fetchInvoices}>Retry</Button>
			</div>
		);
	}

	if (items.length === 0 && !loading) {
		return (
			<div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border/70 bg-background/50 p-12 text-center">
				<div className="mb-6">
					<svg
						className="mx-auto h-24 w-24 text-muted-foreground"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						aria-hidden="true"
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							strokeWidth={1.5}
							d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
						/>
					</svg>
				</div>
				<h3 className="mb-2 text-lg font-semibold text-foreground">
					No Invoices Yet
				</h3>
				<p className="mb-6 max-w-md text-muted-foreground">
					Get started by uploading your first invoice or configure
					email polling to automatically import invoices from your
					inbox.
				</p>
				<div className="flex gap-3">
					<Button
						onClick={() => {
							/* Navigate to upload page */
							window.location.href = "/upload";
						}}
						variant="default"
					>
						Upload Invoice
					</Button>
					<Button onClick={handleManualRefresh} variant="outline">
						Refresh
					</Button>
				</div>
			</div>
		);
	}

	return (
		<div className="w-full space-y-4">
			<div className="flex flex-col gap-3 rounded-2xl border border-border/70 bg-background/50 p-4 sm:flex-row sm:items-center sm:justify-between">
				<div className="flex flex-wrap items-center gap-2">
					<Badge
						variant="outline"
						className="rounded-full border-border/70 bg-card px-3 py-1 text-xs text-muted-foreground"
					>
						{items.length} records
					</Badge>
					<Badge
						variant="outline"
						className="rounded-full border-border/70 bg-card px-3 py-1 text-xs text-muted-foreground"
					>
						Sorted by newest import
					</Badge>
				</div>
				<div className="flex items-center gap-3">
					<Button
						onClick={handleManualRefresh}
						disabled={loading}
						variant="outline"
						size="sm"
						className="flex items-center gap-2"
					>
						<RefreshCw
							className={`h-4 w-4 ${
								loading ? "animate-spin" : ""
							}`}
						/>
						Refresh
					</Button>
				</div>
			</div>

			<div className="overflow-hidden rounded-2xl border border-border/70 bg-background/40">
				<div className="hidden grid-cols-[1.4fr_1fr_0.9fr_0.8fr_96px] gap-4 border-b border-border/70 px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground lg:grid">
					<div>Vendor & Invoice</div>
					<div>Recorded</div>
					<div>Category</div>
					<div>Amount</div>
					<div className="text-right">Action</div>
				</div>
				<div className="max-h-[520px] overflow-y-auto">
					{items.map((item) => (
						<div
							key={item.id}
							className="border-b border-border/70 px-4 py-4 last:border-b-0 lg:px-5"
						>
							<div className="grid gap-4 lg:grid-cols-[1.4fr_1fr_0.9fr_0.8fr_96px] lg:items-center">
								<div className="space-y-2">
									<div className="flex flex-wrap items-center gap-2">
										<p className="font-medium text-foreground">
											{item.vendor_name || "Unknown vendor"}
										</p>
										<Badge
											variant="outline"
											className="rounded-full border-border/70 bg-card text-[11px] text-muted-foreground"
										>
											{item.invoice_number || "No invoice #"}
										</Badge>
									</div>
									<p className="text-sm text-muted-foreground">
										Imported{" "}
										{formatDate(item.created_at)}
									</p>
								</div>

								<div className="space-y-1 text-sm">
									<p className="text-muted-foreground">
										Invoice date
									</p>
									<p className="font-medium text-foreground">
										{formatDate(item.date)}
									</p>
								</div>

								<div className="space-y-1 text-sm">
									<p className="text-muted-foreground">
										Category
									</p>
									<p className="font-medium text-foreground">
										{item.category || "Unclassified"}
									</p>
								</div>

								<div className="space-y-1 text-sm">
									<p className="text-muted-foreground">
										Amount
									</p>
									<p className="font-medium text-foreground">
										{formatCurrency(item.total_amount)}
									</p>
								</div>

								<div className="flex items-center lg:justify-end">
									<Button
										onClick={() => handleOpenDialog(item)}
										size="sm"
									>
										Review
									</Button>
								</div>
							</div>
						</div>
					))}
				</div>
			</div>

			{/* Invoice Edit/Review Dialog */}
			{selectedInvoice && (
				<InvoiceEditDialog
					invoice={selectedInvoice}
					open={dialogOpen}
					onOpenChange={setDialogOpen}
					onSuccess={fetchInvoices}
				/>
			)}
		</div>
	);
}
