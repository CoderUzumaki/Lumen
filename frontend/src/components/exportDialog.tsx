"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { FileDown, Filter } from "lucide-react";
import { invoiceApi } from "@/lib/api/client";

interface ExportDialogProps {
  variant?: "default" | "secondary";
  size?: "default" | "sm" | "lg" | "icon";
  className?: string;
}

export function ExportDialog({
  variant = "default",
  size = "sm",
  className = "",
}: ExportDialogProps) {
  const [open, setOpen] = useState(false);
  const [format, setFormat] = useState<"csv" | "json">("csv");
  const [exporting, setExporting] = useState(false);

  // Filter states
  const [status, setStatus] = useState<string>("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [vendorName, setVendorName] = useState("");

  const handleExport = async () => {
    try {
      setExporting(true);

      const params: {
        format: "csv" | "json";
        status?: string;
        start_date?: string;
        end_date?: string;
        min_amount?: number;
        max_amount?: number;
        vendor_name?: string;
      } = {
        format,
      };

      // Add filters only if they have values
      if (status) params.status = status;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      if (minAmount) params.min_amount = parseFloat(minAmount);
      if (maxAmount) params.max_amount = parseFloat(maxAmount);
      if (vendorName) params.vendor_name = vendorName;

      await invoiceApi.exportInvoices(params);

      // Close dialog after successful export
      setOpen(false);

      // Reset filters
      resetFilters();
    } catch (error) {
      console.error("Export failed:", error);
      alert("Export failed. Please try again.");
    } finally {
      setExporting(false);
    }
  };

  const resetFilters = () => {
    setStatus("");
    setStartDate("");
    setEndDate("");
    setMinAmount("");
    setMaxAmount("");
    setVendorName("");
    setFormat("csv");
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant={variant} size={size} className={className}>
          <FileDown className="w-4 h-4 mr-2" />
          Export
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl bg-linear-to-b from-[#0b0612] to-[#05020a] border-neutral-800">
        <DialogHeader>
          <DialogTitle className="text-2xl font-semibold text-white flex items-center gap-2">
            <FileDown className="w-6 h-6" />
            Export Invoices
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 mt-4">
          {/* Format Selection */}
          <div className="space-y-2">
            <Label className="text-white text-sm font-medium">
              Export Format
            </Label>
            <div className="flex gap-3">
              <Button
                type="button"
                variant={format === "csv" ? "default" : "outline"}
                onClick={() => setFormat("csv")}
                className="flex-1"
              >
                CSV
              </Button>
              <Button
                type="button"
                variant={format === "json" ? "default" : "outline"}
                onClick={() => setFormat("json")}
                className="flex-1"
              >
                JSON
              </Button>
            </div>
          </div>

          {/* Filters Section */}
          <div className="border-t border-neutral-700 pt-4">
            <div className="flex items-center gap-2 mb-4">
              <Filter className="w-4 h-4 text-neutral-400" />
              <h3 className="text-white text-sm font-medium">
                Filters (Optional)
              </h3>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* Status Filter */}
              <div className="space-y-2">
                <Label className="text-neutral-300 text-sm">Status</Label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-md text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">All</option>
                  <option value="completed">Completed</option>
                  <option value="pending">Pending</option>
                  <option value="processing">Processing</option>
                  <option value="failed">Failed</option>
                </select>
              </div>

              {/* Vendor Name Filter */}
              <div className="space-y-2">
                <Label className="text-neutral-300 text-sm">Vendor Name</Label>
                <Input
                  type="text"
                  value={vendorName}
                  onChange={(e) => setVendorName(e.target.value)}
                  placeholder="Search vendor..."
                  className="bg-neutral-900 border-neutral-700 text-white"
                />
              </div>

              {/* Start Date */}
              <div className="space-y-2">
                <Label className="text-neutral-300 text-sm">Start Date</Label>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="bg-neutral-900 border-neutral-700 text-white"
                />
              </div>

              {/* End Date */}
              <div className="space-y-2">
                <Label className="text-neutral-300 text-sm">End Date</Label>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="bg-neutral-900 border-neutral-700 text-white"
                />
              </div>

              {/* Min Amount */}
              <div className="space-y-2">
                <Label className="text-neutral-300 text-sm">Min Amount</Label>
                <Input
                  type="number"
                  value={minAmount}
                  onChange={(e) => setMinAmount(e.target.value)}
                  placeholder="0.00"
                  step="0.01"
                  className="bg-neutral-900 border-neutral-700 text-white"
                />
              </div>

              {/* Max Amount */}
              <div className="space-y-2">
                <Label className="text-neutral-300 text-sm">Max Amount</Label>
                <Input
                  type="number"
                  value={maxAmount}
                  onChange={(e) => setMaxAmount(e.target.value)}
                  placeholder="0.00"
                  step="0.01"
                  className="bg-neutral-900 border-neutral-700 text-white"
                />
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4 border-t border-neutral-700">
            <Button
              type="button"
              variant="outline"
              onClick={resetFilters}
              className="flex-1"
            >
              Reset
            </Button>
            <Button
              type="button"
              onClick={handleExport}
              disabled={exporting}
              className="flex-1"
            >
              {exporting ? "Exporting..." : "Export"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}