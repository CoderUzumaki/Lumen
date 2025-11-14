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
import { invoiceApi } from "@/lib/api/client";
import { eventBus, EVENTS } from "@/lib/events";

interface Invoice {
  id: number;
  file_name: string;
  invoice_id: string | null;
  vendor_name: string | null;
  amount_due: number | null;
  due_date: string | null;
  invoice_date: string | null;
  currency_code: string | null;
  confidence_score: number | null;
  status: string;
  created_at: string;
  updated_at: string;
  owner_id: number;
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
  const [invoiceId, setInvoiceId] = useState(invoice.invoice_id || "");
  const [vendorName, setVendorName] = useState(invoice.vendor_name || "");
  const [amountDue, setAmountDue] = useState(
    invoice.amount_due?.toString() || ""
  );
  const [currencyCode, setCurrencyCode] = useState(
    invoice.currency_code || "USD"
  );
  const [invoiceDate, setInvoiceDate] = useState(invoice.invoice_date || "");
  const [dueDate, setDueDate] = useState(invoice.due_date || "");

  const handleSaveAndApprove = async () => {
    try {
      setSaving(true);

      const updateData: {
        status: string;
        invoice_id?: string;
        vendor_name?: string;
        amount_due?: number;
        currency_code?: string;
        invoice_date?: string;
        due_date?: string;
      } = {
        status: "completed",
      };

      // Only include changed fields
      if (invoiceId !== invoice.invoice_id) updateData.invoice_id = invoiceId;
      if (vendorName !== invoice.vendor_name)
        updateData.vendor_name = vendorName;
      if (amountDue !== invoice.amount_due?.toString())
        updateData.amount_due = parseFloat(amountDue);
      if (currencyCode !== invoice.currency_code)
        updateData.currency_code = currencyCode;
      if (invoiceDate !== invoice.invoice_date)
        updateData.invoice_date = invoiceDate;
      if (dueDate !== invoice.due_date) updateData.due_date = dueDate;

      await invoiceApi.updateInvoice(invoice.id.toString(), updateData);

      // Emit event to refresh all invoice lists
      eventBus.emit(EVENTS.INVOICE_UPDATED);

      // Close dialog and refresh
      onOpenChange(false);
      onSuccess();
    } catch (error) {
      console.error("Error updating invoice:", error);
      alert("Failed to update invoice. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleApproveOnly = async () => {
    try {
      setSaving(true);
      // Update status to "completed" (backend status for approved invoices)
      await invoiceApi.updateInvoice(invoice.id.toString(), {
        status: "completed",
      });

      // Emit event to refresh all invoice lists
      eventBus.emit(EVENTS.INVOICE_UPDATED);

      onOpenChange(false);
      onSuccess();
    } catch (error) {
      console.error("Error approving invoice:", error);
      alert("Failed to approve invoice. Please try again.");
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
              <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                <h3 className="text-sm font-medium text-gray-700 mb-2">
                  Confidence Score
                </h3>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-primary h-2 rounded-full transition-all"
                      style={{
                        width: `${(invoice.confidence_score || 0) * 100}%`,
                      }}
                    />
                  </div>
                  <span className="text-gray-800 font-medium">
                    {((invoice.confidence_score || 0) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Invoice ID */}
              <div className="space-y-2">
                <Label className="text-gray-700 text-sm font-medium">
                  Invoice ID
                </Label>
                <Input
                  type="text"
                  value={invoiceId}
                  onChange={(e) => setInvoiceId(e.target.value)}
                  placeholder="Enter invoice ID"
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
                  onChange={(e) => setVendorName(e.target.value)}
                  placeholder="Enter vendor name"
                  className="bg-white border-gray-300 text-gray-900"
                />
              </div>

              {/* Amount and Currency */}
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2 space-y-2">
                  <Label className="text-gray-700 text-sm font-medium">
                    Amount Due
                  </Label>
                  <Input
                    type="number"
                    value={amountDue}
                    onChange={(e) => setAmountDue(e.target.value)}
                    placeholder="0.00"
                    step="0.01"
                    className="bg-white border-gray-300 text-gray-900"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-gray-700 text-sm font-medium">
                    Currency
                  </Label>
                  <select
                    value={currencyCode}
                    onChange={(e) => setCurrencyCode(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-gray-300 rounded-md text-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-primary h-10"
                  >
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                    <option value="INR">INR</option>
                    <option value="CAD">CAD</option>
                    <option value="AUD">AUD</option>
                    <option value="JPY">JPY</option>
                  </select>
                </div>
              </div>

              {/* Invoice Date */}
              <div className="space-y-2">
                <Label className="text-gray-700 text-sm font-medium">
                  Invoice Date
                </Label>
                <Input
                  type="date"
                  value={invoiceDate}
                  onChange={(e) => setInvoiceDate(e.target.value)}
                  className="bg-white border-gray-300 text-gray-900"
                />
              </div>

              {/* Due Date */}
              <div className="space-y-2">
                <Label className="text-gray-700 text-sm font-medium">
                  Due Date
                </Label>
                <Input
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className="bg-white border-gray-300 text-gray-900"
                />
              </div>

              {/* Action Buttons */}
              <div className="space-y-3 pt-4 border-t border-gray-300">
                <Button
                  onClick={handleSaveAndApprove}
                  disabled={saving}
                  className="w-full"
                >
                  <Save className="w-4 h-4 mr-2" />
                  {saving ? "Saving..." : "Save & Approve"}
                </Button>
                <Button
                  onClick={handleApproveOnly}
                  disabled={saving}
                  variant="outline"
                  className="w-full border-gray-300 hover:bg-gray-100"
                >
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Approve Without Changes
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

              {/* File Info */}
              <div className="bg-white p-4 rounded-lg border border-gray-300 shadow-sm">
                <div className="flex items-start gap-3">
                  <FileText className="w-5 h-5 text-gray-600 mt-1" />
                  <div className="flex-1">
                    <h4 className="text-sm font-medium text-gray-800 mb-1">
                      Source File
                    </h4>
                    <p className="text-sm text-gray-600 break-all">
                      {invoice.file_name}
                    </p>
                  </div>
                </div>
              </div>

              {/* Current Data Preview */}
              <div className="bg-white p-4 rounded-lg border border-gray-300 shadow-sm space-y-3">
                <h4 className="text-sm font-medium text-gray-800 mb-3">
                  Current Invoice Data
                </h4>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-gray-600">Invoice ID:</span>
                    <p className="text-gray-900 font-medium mt-1">
                      {invoice.invoice_id || "N/A"}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-600">Status:</span>
                    <p className="text-gray-900 font-medium mt-1">
                      <span
                        className={`inline-block px-2 py-1 rounded text-xs ${
                          invoice.status === "completed"
                            ? "bg-green-100 text-green-700"
                            : invoice.status === "failed"
                            ? "bg-red-100 text-red-700"
                            : invoice.status === "processing"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-yellow-100 text-yellow-700"
                        }`}
                      >
                        {invoice.status === "completed"
                          ? "Completed"
                          : invoice.status === "failed"
                          ? "Failed"
                          : invoice.status === "processing"
                          ? "Processing"
                          : "Pending"}
                      </span>
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-600">Vendor:</span>
                    <p className="text-gray-900 font-medium mt-1">
                      {invoice.vendor_name || "N/A"}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-600">Amount:</span>
                    <p className="text-gray-900 font-medium mt-1">
                      {invoice.currency_code || "USD"}{" "}
                      {invoice.amount_due?.toFixed(2) || "0.00"}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-600">Invoice Date:</span>
                    <p className="text-gray-900 font-medium mt-1">
                      {invoice.invoice_date || "N/A"}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-600">Due Date:</span>
                    <p className="text-gray-900 font-medium mt-1">
                      {invoice.due_date || "N/A"}
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
                    Created: {new Date(invoice.created_at).toLocaleString()}
                  </p>
                  <p>
                    Updated: {new Date(invoice.updated_at).toLocaleString()}
                  </p>
                </div>
              </div>

              {/* Note */}
              <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>Note:</strong> Review the extracted data on the left
                  and make any necessary corrections before approving the
                  invoice.
                </p>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}