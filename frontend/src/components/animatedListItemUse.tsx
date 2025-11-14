"use client";
import AnimatedList from "./AnimatedList";
import { useEffect, useState } from "react";
import { Button } from "./ui/button";
import { InvoiceEditDialog } from "@/components/invoiceEditDialog";
import { RefreshCw } from "lucide-react";
import { transactionApi } from "@/lib/api/client";
import { eventBus, EVENTS } from "@/lib/events";

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
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const fetchInvoices = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch from database API
      const userId = "123"; // TODO: Get from auth context
      const response = await transactionApi.getTransactions(userId, {
        page: 1,
        page_size: 100,
        sort_by: "created_at",
        sort_order: "desc",
      });

      if (response.success && response.data) {
        console.log("Fetched transactions from database:", response.data);
        setItems(response.data);
      } else {
        setItems([]);
      }
    } catch (error) {
      console.error("Error fetching transactions:", error);

      // Fallback to localStorage if API fails
      try {
        const storedInvoices = localStorage.getItem("invoices");
        const invoices = storedInvoices ? JSON.parse(storedInvoices) : [];
        console.log("Using localStorage fallback:", invoices);
        setItems(invoices);
      } catch (localError) {
        setItems([]);
      }

      const errorMessage =
        error instanceof Error ? error.message : "Failed to fetch transactions";
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
    fetchInvoices();

    // Listen for invoice updates
    const handleInvoiceUpdate = () => {
      fetchInvoices();
    };

    eventBus.on(EVENTS.INVOICE_UPDATED, handleInvoiceUpdate);

    return () => {
      eventBus.off(EVENTS.INVOICE_UPDATED, handleInvoiceUpdate);
    };
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
    return {
      invoiceNumber: item.invoice_number || "N/A",
      invoiceDate: item.date || "N/A",
      dueDate: "N/A", // Not in Transaction model
      amountPayable: item.total_amount?.toString() || "N/A",
      currency: "USD", // Not in Transaction model
      vendorName: item.vendor_name || "N/A",
      customerName: "N/A", // Not in Transaction model
      ConfidenceScore: "N/A", // Not in Transaction model
      status: item.category || "Other", // Using category as status display
      actions: (
        <Button
          onClick={(e) => {
            e.stopPropagation();
            handleOpenDialog(item);
          }}
          variant="default"
          size="sm"
        >
          Edit
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
        </div>
      </div>

      <AnimatedList
        items={transformedItems}
        onItemSelect={(item, index) => console.log("Selected:", item, index)}
        showGradients={false}
        enableArrowNavigation={true}
        displayScrollbar={true}
        className="w-full max-w-full"
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
