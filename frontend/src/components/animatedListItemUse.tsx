"use client";
import AnimatedList from "./AnimatedList";
import { invoiceApi, emailConfigApi } from "@/lib/api/client";
import { useEffect, useState, useRef, useCallback } from "react";
import { Button } from "./ui/button";
import { InvoiceEditDialog } from "@/components/invoiceEditDialog";
import { RefreshCw, Pause, Play, Mail, Settings } from "lucide-react";

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

export default function AnimatedListItemUse() {
  const [items, setItems] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [isAutoRefresh, setIsAutoRefresh] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [lastPollTime, setLastPollTime] = useState<Date | null>(null);
  const [emailConfigured, setEmailConfigured] = useState(false);
  const [backendPollingEnabled, setBackendPollingEnabled] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchEmailStatus = async () => {
    try {
      const status = await emailConfigApi.getStatus();
      setEmailConfigured(status.configured);
      setBackendPollingEnabled(status.polling_enabled);
      if (status.last_poll_time) {
        setLastPollTime(new Date(status.last_poll_time));
      }
    } catch (error) {
      console.error("Error fetching email status:", error);
      setEmailConfigured(false);
      setBackendPollingEnabled(false);
    }
  };

  const fetchInvoices = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await invoiceApi.getMyInvoices();
      console.log("Fetched invoices:", data);
      // Backend2 returns paginated data with { total, invoices, page, page_size }
      setItems(data.invoices || []);
    } catch (error) {
      console.error("Error fetching invoices:", error);
      // If 404, it means no invoices yet - not an error
      if ((error as any)?.response?.status === 404) {
        setItems([]);
        setError(null);
      } else {
        const errorMessage =
          error instanceof Error ? error.message : "Failed to fetch invoices";
        setError(errorMessage);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleManualRefresh = async () => {
    await fetchInvoices();
    await fetchEmailStatus();
  };

  const handlePollEmails = useCallback(async () => {
    try {
      setIsPolling(true);
      const result = await emailConfigApi.pollNow();
      console.log("Email polling result:", result);
      setLastPollTime(new Date());

      // Refresh the invoice list to show new invoices
      const data = await invoiceApi.getMyInvoices();
      setItems(data.invoices || []);

      // Show a notification about the result
      if (result.invoices_created > 0) {
        alert(`✅ ${result.invoices_created} new invoice(s) found and added!`);
      } else if (result.emails_checked === 0) {
        alert("📭 No new emails found.");
      } else {
        alert("ℹ️ Emails checked, but no invoices found.");
      }
    } catch (error) {
      console.error("Error polling emails:", error);
      const errorMsg = error instanceof Error ? error.message : "Unknown error";
      if (errorMsg.includes("Email configuration not found")) {
        alert(
          "❌ Email not configured. Please configure your email in settings first."
        );
      } else {
        alert(`❌ Failed to poll emails: ${errorMsg}`);
      }
    } finally {
      setIsPolling(false);
    }
  }, []);

  const toggleBackendPolling = async () => {
    try {
      if (backendPollingEnabled) {
        await emailConfigApi.pausePolling();
        setBackendPollingEnabled(false);
        alert("⏸️ Backend email polling paused");
      } else {
        await emailConfigApi.resumePolling();
        setBackendPollingEnabled(true);
        alert("▶️ Backend email polling resumed");
      }
    } catch (error) {
      console.error("Error toggling backend polling:", error);
      const errorMsg = error instanceof Error ? error.message : "Unknown error";
      if (errorMsg.includes("Email configuration not found")) {
        alert(
          "❌ Email not configured. Please configure your email in settings first."
        );
      } else {
        alert(`❌ Failed to toggle polling: ${errorMsg}`);
      }
    }
  };

  const toggleAutoRefresh = () => {
    setIsAutoRefresh(!isAutoRefresh);
  };

  // Auto-refresh effect
  useEffect(() => {
    const pollAndRefresh = async () => {
      await handlePollEmails();
    };

    if (isAutoRefresh) {
      // Poll immediately when enabled
      pollAndRefresh();

      // Set up interval to poll every 30 seconds
      intervalRef.current = setInterval(() => {
        pollAndRefresh();
      }, 30000); // 30 seconds
    } else {
      // Clear interval when disabled
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    // Cleanup on unmount
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isAutoRefresh, handlePollEmails]);

  useEffect(() => {
    fetchInvoices();
    fetchEmailStatus();
  }, []);

  const handleOpenDialog = (invoice: Invoice) => {
    setSelectedInvoice(invoice);
    setDialogOpen(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        <span className="ml-3">Loading invoices...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-500 mb-4">{error}</p>
        <Button onClick={fetchInvoices}>Retry</Button>
      </div>
    );
  }

  if (items.length === 0 && !loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center">
        <div className="mb-6">
          <svg
            className="mx-auto h-24 w-24 text-gray-400"
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
        <h3 className="text-lg font-semibold text-foreground mb-2">
          No Invoices Yet
        </h3>
        <p className="text-muted-foreground mb-6 max-w-md">
          Get started by uploading your first invoice or configure email polling
          to automatically import invoices from your inbox.
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

  // Transform backend data to match the AnimatedList component format
  const transformedItems = items.map((item) => {
    // Backend uses: "pending", "processing", "completed", "failed"
    // Use database status directly - don't filter by confidence score
    const isCompleted = item.status === "completed";
    const isFailed = item.status === "failed";
    const needsReview =
      item.status === "pending" || item.status === "processing" || isFailed;

    return {
      invoiceNumber: item.invoice_id || "N/A",
      invoiceDate: item.invoice_date || "N/A",
      dueDate: item.due_date || "N/A",
      amountPayable: item.amount_due?.toString() || "N/A",
      currency: item.currency_code || "USD",
      vendorName: item.vendor_name || "N/A",
      customerName: "N/A", // Backend doesn't have customer name
      ConfidenceScore: item.confidence_score
        ? `${(item.confidence_score * 100).toFixed(0)}%`
        : "N/A",
      status: item.status, // Use actual database status
      actions: (
        <Button
          onClick={(e) => {
            e.stopPropagation();
            handleOpenDialog(item);
          }}
          variant={
            isCompleted ? "secondary" : needsReview ? "default" : "default"
          }
          size="sm"
          className={
            isFailed
              ? "bg-red-500 hover:bg-red-600 text-white"
              : needsReview
              ? "bg-orange-500 hover:bg-orange-600 text-white"
              : ""
          }
        >
          {isCompleted ? "View" : isFailed ? "Fix" : "Review"}
        </Button>
      ),
    };
  });

  return (
    <div className="w-full">
      {/* Control Panel */}
      <div className="mb-4 p-4 bg-white rounded-lg border border-gray-200 shadow-sm">
        <div className="flex items-center gap-3 flex-wrap">
          <Button
            onClick={handleManualRefresh}
            disabled={loading}
            variant="outline"
            size="sm"
            className="flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Button
            onClick={handlePollEmails}
            disabled={isPolling || loading || !emailConfigured}
            variant="outline"
            size="sm"
            className="flex items-center gap-2"
            title={
              !emailConfigured ? "Configure email first" : "Check emails now"
            }
          >
            <Mail className={`w-4 h-4 ${isPolling ? "animate-pulse" : ""}`} />
            {isPolling ? "Checking..." : "Check Emails Now"}
          </Button>

          <Button
            onClick={toggleAutoRefresh}
            variant={isAutoRefresh ? "default" : "outline"}
            size="sm"
            className="flex items-center gap-2"
            title="Frontend auto-refresh (30s)"
          >
            {isAutoRefresh ? (
              <>
                <Pause className="w-4 h-4" />
                Pause UI Refresh
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Auto UI Refresh
              </>
            )}
          </Button>

          <div className="h-6 w-px bg-gray-300"></div>

          <Button
            onClick={toggleBackendPolling}
            disabled={!emailConfigured}
            variant={backendPollingEnabled ? "default" : "outline"}
            size="sm"
            className={`flex items-center gap-2 ${
              backendPollingEnabled ? "bg-green-600 hover:bg-green-700" : ""
            }`}
            title={
              !emailConfigured
                ? "Configure email first"
                : backendPollingEnabled
                ? "Backend polling active"
                : "Backend polling paused"
            }
          >
            <Settings
              className={`w-4 h-4 ${
                backendPollingEnabled ? "animate-spin-slow" : ""
              }`}
            />
            {backendPollingEnabled ? "Backend: Active" : "Backend: Paused"}
          </Button>

          {!emailConfigured && (
            <span className="text-xs text-orange-600 font-medium">
              ⚠️ Email not configured
            </span>
          )}

          {lastPollTime && (
            <span className="text-xs text-gray-500 ml-auto">
              Last: {lastPollTime.toLocaleTimeString()}
            </span>
          )}
        </div>

        {emailConfigured && (
          <div className="mt-2 text-xs text-gray-600">
            <span className="font-medium">Backend Status:</span>{" "}
            {backendPollingEnabled ? (
              <span className="text-green-600">✓ Auto-polling enabled</span>
            ) : (
              <span className="text-orange-600">⏸ Auto-polling paused</span>
            )}
          </div>
        )}
      </div>

      <AnimatedList
        items={transformedItems}
        onItemSelect={(item, index) => console.log("Selected:", item, index)}
        showGradients={false}
        enableArrowNavigation={true}
        displayScrollbar={true}
      />

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