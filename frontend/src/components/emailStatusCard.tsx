"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Mail, RefreshCw, Pause, Play, Settings } from "lucide-react";
import { emailConfigApi } from "@/lib/api/client";
import { toast } from "@/lib/toast";
import { EmailConfigDialog } from "./emailConfigDialog";

export function EmailStatusCard() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchStatus = async () => {
    try {
      const data = await emailConfigApi.getStatus();
      setStatus(data);
    } catch (error) {
      console.error("Error fetching email status:", error);
      setStatus(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    // Refresh status every 30 seconds
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleTogglePolling = async () => {
    setActionLoading(true);
    try {
      if (status?.polling_enabled) {
        await emailConfigApi.pausePolling();
      } else {
        await emailConfigApi.resumePolling();
      }
      await fetchStatus();
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : "Unknown error";
      toast.error(`Failed to toggle polling: ${message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handlePollNow = async () => {
    setActionLoading(true);
    try {
      const result = await emailConfigApi.pollNow();
      toast.success(
        `Polling complete! Checked ${result.emails_checked} emails, created ${result.invoices_created} invoices.`
      );
      await fetchStatus();
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : "Unknown error";
      toast.error(`Failed to poll emails: ${message}`);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="@container/card">
        <CardHeader>
          <div className="h-4 w-24 bg-muted rounded animate-pulse mb-2"></div>
          <div className="h-8 w-16 bg-muted rounded animate-pulse"></div>
        </CardHeader>
      </Card>
    );
  }

  if (!status || !status.configured) {
    return (
      <Card className="@container/card bg-gradient-to-br from-blue-500/10 via-blue-500/5 to-card shadow-sm border-blue-500/20 overflow-hidden">
        <CardHeader>
          <CardDescription>Email Polling</CardDescription>
          <CardTitle className="text-2xl font-semibold text-blue-700 dark:text-blue-400">
            Not Configured
          </CardTitle>
        </CardHeader>
        <CardFooter className="w-full">
          <EmailConfigDialog onConfigured={() => fetchStatus()} />
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card className="@container/card bg-gradient-to-br from-purple-500/10 via-purple-500/5 to-card shadow-sm border-purple-500/20 overflow-hidden">
      <CardHeader className="max-w-full">
        <div className="flex items-center justify-between">
          <CardDescription>Email Polling</CardDescription>
          <Badge
            variant={status.polling_enabled ? "default" : "secondary"}
            className={status.polling_enabled ? "bg-green-500" : "bg-gray-500"}
          >
            {status.polling_enabled ? "Active" : "Paused"}
          </Badge>
        </div>
        <CardTitle className="text-base md:text-lg font-semibold text-purple-700 dark:text-purple-400 flex items-center gap-2 w-full min-w-0">
          <Mail className="h-4 w-4 md:h-5 md:w-5 shrink-0" />
          <span className="truncate overflow-hidden text-ellipsis">
            {status.email_address}
          </span>
        </CardTitle>
      </CardHeader>
      <CardFooter className="flex-col items-start gap-2">
        <div className="text-sm text-muted-foreground space-y-1 w-full">
          <div className="flex justify-between items-center gap-2">
            <span className="shrink-0">Folder:</span>
            <span className="font-medium truncate text-right">
              {status.folder_to_watch}
            </span>
          </div>
          <div className="flex justify-between items-center gap-2">
            <span className="shrink-0">Interval:</span>
            <span className="font-medium truncate text-right">
              {status.polling_interval_minutes} min
            </span>
          </div>
          <div className="flex justify-between items-center gap-2">
            <span className="shrink-0">Last Check:</span>
            <span className="font-medium truncate text-right">
              {status.last_poll_time
                ? new Date(status.last_poll_time).toLocaleString()
                : "Never"}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 mt-2 w-full">
          <Button
            size="sm"
            variant="outline"
            onClick={handleTogglePolling}
            disabled={actionLoading}
            className="flex-1 min-w-[80px]"
          >
            {status.polling_enabled ? (
              <>
                <Pause className="h-4 w-4 mr-1" />
                Pause
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-1" />
                Resume
              </>
            )}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handlePollNow}
            disabled={actionLoading}
            className="flex-1 min-w-[80px]"
          >
            <RefreshCw className="h-4 w-4 mr-1" />
            Poll Now
          </Button>
          <EmailConfigDialog
            existingConfig={status}
            onConfigured={() => fetchStatus()}
          />
        </div>
      </CardFooter>
    </Card>
  );
}