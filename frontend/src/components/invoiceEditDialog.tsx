"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { FileText, Save, CheckCircle } from "lucide-react";
import { eventBus, EVENTS } from "@/lib/events";
import { transactionApi } from "@/lib/api/client";
import { toast } from "@/lib/toast";

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
	updated_at?: string;
	items?: Array<{
		item_name: string;
		quantity: number;
		unit_price: number;
		total_price: number;
	}>;
}

interface InvoiceEditDialogProps {
	invoice: Invoice;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onSuccess: () => void;
}

export function InvoiceEditDialog({
	invoice,
	open,
	onOpenChange,
	onSuccess,
}: InvoiceEditDialogProps) {
	const [saving, setSaving] = useState(false);

	// Editable fields
	const [invoiceNumber, setInvoiceNumber] = useState(
		invoice.invoice_number || ""
	);
	const [vendorName, setVendorName] = useState(invoice.vendor_name || "");
	const [totalAmount, setTotalAmount] = useState(
		invoice.total_amount?.toString() || ""
	);
	const [taxAmount, setTaxAmount] = useState(
		invoice.tax_amount?.toString() || ""
	);
	const [date, setDate] = useState(invoice.date || "");
	const [category, setCategory] = useState(invoice.category || "Other");
	const [paymentMethod, setPaymentMethod] = useState(
		invoice.payment_method || ""
	);
	const [address, setAddress] = useState(invoice.address || "");

	const handleSaveAndApprove = async () => {
		try {
			setSaving(true);

			// Update via database API
			const updateData = {
				vendor_name: vendorName,
				invoice_number: invoiceNumber,
				date: date,
				total_amount: parseFloat(totalAmount) || 0,
				tax_amount: parseFloat(taxAmount) || 0,
				payment_method: paymentMethod,
				address: address,
				category: category,
			};

			const response = await transactionApi.updateTransaction(
				invoice.id,
				updateData
			);

			if (response.success) {
				// Emit event to refresh all invoice lists
				eventBus.emit(EVENTS.INVOICE_UPDATED);

				// Close dialog and refresh
				onOpenChange(false);
				onSuccess();
			} else {
				throw new Error("Failed to update transaction");
			}
		} catch (error) {
			console.error("Error updating invoice:", error);
			toast.error("Failed to update invoice. Please try again.");
		} finally {
			setSaving(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-[1400px]! w-full h-[90vh] bg-linear-to-br from-slate-50 to-gray-100 border-gray-300 p-0">
				<DialogHeader className="px-6 pt-6 pb-4 border-b border-gray-300 bg-white/80">
					<DialogTitle className="text-2xl font-semibold text-gray-800 flex items-center gap-2">
						<FileText className="w-6 h-6 text-primary" />
						Review & Edit Invoice
					</DialogTitle>
				</DialogHeader>

				<div className="flex h-full overflow-hidden">
					{/* Left Side: Edit Form */}
					<div className="w-1/2 p-6 overflow-y-auto border-r border-gray-300 bg-white/50">
						<div className="space-y-4">
							{/* Invoice Number */}
							<div className="space-y-2">
								<Label className="text-gray-700 text-sm font-medium">
									Invoice Number
								</Label>
								<Input
									type="text"
									value={invoiceNumber}
									onChange={(e) =>
										setInvoiceNumber(e.target.value)
									}
									placeholder="Enter invoice number"
									className="bg-white border-gray-300 text-gray-900"
								/>
							</div>
							{/* Vendor Name */}
							<div className="space-y-2">
								<Label className="text-gray-700 text-sm font-medium">
									Vendor Name
								</Label>
								<Input
									type="text"
									value={vendorName}
									onChange={(e) =>
										setVendorName(e.target.value)
									}
									placeholder="Enter vendor name"
									className="bg-white border-gray-300 text-gray-900"
								/>
							</div>
							{/* Total Amount */}
							<div className="space-y-2">
								<Label className="text-gray-700 text-sm font-medium">
									Total Amount
								</Label>
								<Input
									type="number"
									value={totalAmount}
									onChange={(e) =>
										setTotalAmount(e.target.value)
									}
									placeholder="0.00"
									step="0.01"
									className="bg-white border-gray-300 text-gray-900"
								/>
							</div>
							{/* Tax Amount */}
							<div className="space-y-2">
								<Label className="text-gray-700 text-sm font-medium">
									Tax Amount
								</Label>
								<Input
									type="number"
									value={taxAmount}
									onChange={(e) =>
										setTaxAmount(e.target.value)
									}
									placeholder="0.00"
									step="0.01"
									className="bg-white border-gray-300 text-gray-900"
								/>
							</div>{" "}
							{/* Transaction Date */}
							<div className="space-y-2">
								<Label className="text-gray-700 text-sm font-medium">
									Transaction Date
								</Label>
								<Input
									type="date"
									value={date}
									onChange={(e) => setDate(e.target.value)}
									className="bg-white border-gray-300 text-gray-900"
								/>
							</div>
							{/* Category */}
							<div className="space-y-2">
								<Label className="text-gray-700 text-sm font-medium">
									Category
								</Label>
								<Input
									type="text"
									value={category}
									onChange={(e) =>
										setCategory(e.target.value)
									}
									placeholder="e.g. Restaurant, Office Supplies"
									className="bg-white border-gray-300 text-gray-900"
								/>
							</div>{" "}
							{/* Action Buttons */}
							<div className="pt-4 border-t border-gray-300">
								<Button
									onClick={handleSaveAndApprove}
									disabled={saving}
									className="w-full"
								>
									<Save className="w-4 h-4 mr-2" />
									{saving ? "Saving..." : "Save Changes"}
								</Button>
							</div>
						</div>
					</div>

					{/* Right Side: Invoice Preview */}
					<div className="w-1/2 p-6 overflow-y-auto bg-slate-50">
						<div className="space-y-4">
							<h3 className="text-lg font-semibold text-gray-800 mb-4">
								Invoice Reference
							</h3>

							{/* Current Data Preview */}
							<div className="bg-white p-4 rounded-lg border border-gray-300 shadow-sm space-y-3">
								<h4 className="text-sm font-medium text-gray-800 mb-3">
									Transaction Details
								</h4>

								<div className="grid grid-cols-2 gap-3 text-sm">
									<div>
										<span className="text-gray-600">
											Database ID:
										</span>
										<p className="text-gray-900 font-mono font-bold mt-1">
											#{invoice.id}
										</p>
									</div>
									<div>
										<span className="text-gray-600">
											Invoice Number:
										</span>
										<p className="text-gray-900 font-medium mt-1">
											{invoice.invoice_number || "N/A"}
										</p>
									</div>
									<div>
										<span className="text-gray-600">
											Vendor:
										</span>
										<p className="text-gray-900 font-medium mt-1">
											{invoice.vendor_name || "N/A"}
										</p>
									</div>
									<div>
										<span className="text-gray-600">
											Total Amount:
										</span>
										<p className="text-gray-900 font-medium mt-1">
											$
											{invoice.total_amount?.toFixed(2) ||
												"0.00"}
										</p>
									</div>
									<div>
										<span className="text-gray-600">
											Tax Amount:
										</span>
										<p className="text-gray-900 font-medium mt-1">
											$
											{invoice.tax_amount?.toFixed(2) ||
												"0.00"}
										</p>
									</div>
									<div>
										<span className="text-gray-600">
											Date:
										</span>
										<p className="text-gray-900 font-medium mt-1">
											{invoice.date || "N/A"}
										</p>
									</div>
									<div>
										<span className="text-gray-600">
											Category:
										</span>
										<p className="text-gray-900 font-medium mt-1">
											{invoice.category || "N/A"}
										</p>
									</div>
									<div>
										<span className="text-gray-600">
											Payment Method:
										</span>
										<p className="text-gray-900 font-medium mt-1">
											{invoice.payment_method || "N/A"}
										</p>
									</div>
								</div>
							</div>

							{/* Metadata */}
							<div className="bg-white p-4 rounded-lg border border-gray-300 shadow-sm space-y-2">
								<h4 className="text-sm font-medium text-gray-800 mb-2">
									Metadata
								</h4>
								<div className="text-xs text-gray-600 space-y-1">
									<p>
										Created:{" "}
										{new Date(
											invoice.created_at
										).toLocaleString()}
									</p>
									<p>
										Updated:{" "}
										{invoice.updated_at
											? new Date(
													invoice.updated_at
												).toLocaleString()
											: new Date(
													invoice.created_at
												).toLocaleString()}
									</p>
								</div>
							</div>

							{/* Note */}
							<div className="bg-blue-50 border border-blue-200 p-4 rounded-lg">
								<p className="text-sm text-blue-800">
									<strong>Note:</strong> Review the extracted
									data on the left and make any necessary
									corrections before approving the invoice.
								</p>
							</div>
						</div>
					</div>
				</div>
			</DialogContent>
		</Dialog>
	);
}
