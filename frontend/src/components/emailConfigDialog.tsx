"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Mail, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { emailConfigApi } from "@/lib/api/client";
import { GmailOAuthButton } from "@/components/gmailOAuthButton";

interface EmailConfigDialogProps {
  onConfigured?: () => void;
  existingConfig?: any;
}

export function EmailConfigDialog({
  onConfigured,
  existingConfig,
}: EmailConfigDialogProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [testPassed, setTestPassed] = useState(false);
  const [authMethod, setAuthMethod] = useState<"oauth" | "imap">("oauth");
  const [isGmailOAuthConnected, setIsGmailOAuthConnected] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    email_address: existingConfig?.email_address || "",
    provider: existingConfig?.provider || "gmail",
    imap_server: existingConfig?.imap_server || "imap.gmail.com",
    imap_port: existingConfig?.imap_port || 993,
    imap_username: existingConfig?.imap_username || "",
    imap_password: "",
    use_ssl: existingConfig?.use_ssl ?? true,
    polling_enabled: existingConfig?.polling_enabled ?? true,
    polling_interval_minutes: existingConfig?.polling_interval_minutes || 1,
    folder_to_watch: existingConfig?.folder_to_watch || "INBOX",
    mark_as_read: existingConfig?.mark_as_read ?? true,
  });

  const emailProviders = [
    { value: "gmail", label: "Gmail", imap: "imap.gmail.com", port: 993 },
    {
      value: "outlook",
      label: "Outlook/Hotmail",
      imap: "outlook.office365.com",
      port: 993,
    },
    { value: "yahoo", label: "Yahoo", imap: "imap.mail.yahoo.com", port: 993 },
    { value: "icloud", label: "iCloud", imap: "imap.mail.me.com", port: 993 },
    { value: "custom", label: "Custom IMAP", imap: "", port: 993 },
  ];

  const handleProviderChange = (provider: string) => {
    const selectedProvider = emailProviders.find((p) => p.value === provider);
    if (selectedProvider && selectedProvider.value !== "custom") {
      setFormData({
        ...formData,
        provider,
        imap_server: selectedProvider.imap,
        imap_port: selectedProvider.port,
      });
    } else {
      setFormData({ ...formData, provider });
    }
    // Reset test state when provider changes
    setTestResult(null);
    setTestPassed(false);
  };

  const handleFormChange = (field: string, value: any) => {
    setFormData({ ...formData, [field]: value });
    // Reset test state when critical fields change
    if (
      [
        "email_address",
        "imap_password",
        "imap_server",
        "imap_port",
        "use_ssl",
      ].includes(field)
    ) {
      setTestResult(null);
      setTestPassed(false);
    }

    // Reset OAuth state when email changes
    if (field === "email_address") {
      setIsGmailOAuthConnected(false);
      setAuthMethod("oauth");
    }
  };

  const isGmailEmail = formData.email_address
    .toLowerCase()
    .endsWith("@gmail.com");

  const handleGmailOAuthSuccess = (email: string) => {
    setIsGmailOAuthConnected(true);
    setTestPassed(true);
    setTestResult({
      success: true,
      message: `Gmail account ${email} connected successfully via OAuth! ✓`,
    });
  };

  const handleGmailOAuthError = (error: string) => {
    setIsGmailOAuthConnected(false);
    setTestPassed(false);
    setTestResult({
      success: false,
      message: `OAuth failed: ${error}`,
    });
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setTestResult(null);
    setTestPassed(false);

    try {
      // First, create or update the config
      const configData = {
        email_address: formData.email_address,
        provider: formData.provider,
        imap_server: formData.imap_server,
        imap_port: formData.imap_port,
        imap_username: formData.imap_username || formData.email_address,
        imap_password: formData.imap_password,
        use_ssl: formData.use_ssl,
        polling_enabled: false, // Don't enable polling yet
        polling_interval_minutes: formData.polling_interval_minutes,
        folder_to_watch: formData.folder_to_watch,
        mark_as_read: formData.mark_as_read,
      };

      if (existingConfig) {
        await emailConfigApi.updateConfig(configData);
      } else {
        await emailConfigApi.createConfig(configData);
      }

      // Now test the connection
      const result = await emailConfigApi.testConnection();
      setTestResult({
        success: true,
        message: result.message || "Connection successful! ✓",
      });
      setTestPassed(true);
    } catch (error: any) {
      const errorDetail =
        error.response?.data?.detail || error.message || "Connection failed";
      setTestResult({
        success: false,
        message: errorDetail,
      });
      setTestPassed(false);
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const configData = {
        email_address: formData.email_address,
        provider: formData.provider,
        imap_server: formData.imap_server,
        imap_port: formData.imap_port,
        imap_username: formData.imap_username || formData.email_address,
        imap_password: formData.imap_password,
        use_ssl: formData.use_ssl,
        polling_enabled: formData.polling_enabled,
        polling_interval_minutes: formData.polling_interval_minutes,
        folder_to_watch: formData.folder_to_watch,
        mark_as_read: formData.mark_as_read,
      };

      if (existingConfig) {
        await emailConfigApi.updateConfig(configData);
      } else {
        await emailConfigApi.createConfig(configData);
      }

      setOpen(false);
      if (onConfigured) {
        onConfigured();
      }
    } catch (error: any) {
      alert(
        `Failed to save configuration: ${
          error.response?.data?.detail || error.message
        }`
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="gap-2">
          <Mail className="h-4 w-4" />
          {existingConfig ? "Edit Email Config" : "Configure Email"}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {existingConfig
              ? "Edit Email Configuration"
              : "Configure Email Polling"}
          </DialogTitle>
          <DialogDescription>
            Connect your email account to automatically import invoices. We&apos;ll
            securely store your credentials and poll your inbox for new
            invoices.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Email Provider */}
          <div className="space-y-2">
            <Label htmlFor="provider">Email Provider</Label>
            <Select
              value={formData.provider}
              onValueChange={handleProviderChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select provider" />
              </SelectTrigger>
              <SelectContent>
                {emailProviders.map((provider) => (
                  <SelectItem key={provider.value} value={provider.value}>
                    {provider.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Email Address */}
          <div className="space-y-2">
            <Label htmlFor="email">Email Address</Label>
            <Input
              id="email"
              type="email"
              placeholder="your.email@example.com"
              value={formData.email_address}
              onChange={(e) =>
                handleFormChange("email_address", e.target.value)
              }
              required
            />
          </div>

          {/* Gmail OAuth or IMAP Authentication */}
          {isGmailEmail ? (
            <div className="space-y-4 p-4 border rounded-lg bg-blue-50 dark:bg-blue-950">
              <div className="space-y-2">
                <Label className="text-base font-semibold">
                  Gmail Authentication Method
                </Label>
                <p className="text-sm text-muted-foreground">
                  Choose how you want to connect your Gmail account
                </p>
              </div>

              <div className="space-y-3">
                {/* OAuth Option */}
                <div className="flex items-start space-x-3">
                  <input
                    type="radio"
                    id="auth-oauth"
                    name="auth-method"
                    value="oauth"
                    checked={authMethod === "oauth"}
                    onChange={(e) => {
                      setAuthMethod("oauth");
                      setTestResult(null);
                      setTestPassed(false);
                    }}
                    className="mt-1 h-4 w-4"
                  />
                  <div className="flex-1">
                    <Label
                      htmlFor="auth-oauth"
                      className="font-medium cursor-pointer"
                    >
                      OAuth 2.0 (Recommended) ⭐
                    </Label>
                    <p className="text-xs text-muted-foreground mt-1">
                      Secure authentication without passwords. More secure and
                      easier to set up.
                    </p>
                  </div>
                </div>

                {/* App Password Option */}
                <div className="flex items-start space-x-3">
                  <input
                    type="radio"
                    id="auth-imap"
                    name="auth-method"
                    value="imap"
                    checked={authMethod === "imap"}
                    onChange={(e) => {
                      setAuthMethod("imap");
                      setTestResult(null);
                      setTestPassed(false);
                      setIsGmailOAuthConnected(false);
                    }}
                    className="mt-1 h-4 w-4"
                  />
                  <div className="flex-1">
                    <Label
                      htmlFor="auth-imap"
                      className="font-medium cursor-pointer"
                    >
                      App Password (Alternative)
                    </Label>
                    <p className="text-xs text-muted-foreground mt-1">
                      Use Gmail App Password for IMAP access
                    </p>
                  </div>
                </div>
              </div>

              {/* Show OAuth Button or Password Field */}
              {authMethod === "oauth" ? (
                <div className="pt-2">
                  <GmailOAuthButton
                    onSuccess={handleGmailOAuthSuccess}
                    onError={handleGmailOAuthError}
                    disabled={!formData.email_address}
                  />
                </div>
              ) : (
                <div className="space-y-2 pt-2">
                  <Label htmlFor="password">Gmail App Password</Label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="Enter your Gmail App Password"
                    value={formData.imap_password}
                    onChange={(e) =>
                      handleFormChange("imap_password", e.target.value)
                    }
                    required={!existingConfig}
                  />
                  <p className="text-xs text-muted-foreground">
                    Generate an{" "}
                    <a
                      href="https://myaccount.google.com/apppasswords"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary underline"
                    >
                      App Password
                    </a>{" "}
                    from your Google Account settings.
                  </p>
                </div>
              )}
            </div>
          ) : (
            /* Non-Gmail Password Field */
            <div className="space-y-2">
              <Label htmlFor="password">Password / App Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter your email password"
                value={formData.imap_password}
                onChange={(e) =>
                  handleFormChange("imap_password", e.target.value)
                }
                required={!existingConfig}
              />
              <p className="text-xs text-muted-foreground">
                Use your email account password or app-specific password.
              </p>
            </div>
          )}

          {/* Advanced Settings */}
          <details className="space-y-4">
            <summary className="cursor-pointer font-medium text-sm">
              Advanced Settings
            </summary>

            <div className="grid grid-cols-2 gap-4 mt-4">
              {/* IMAP Server */}
              <div className="space-y-2">
                <Label htmlFor="imap_server">IMAP Server</Label>
                <Input
                  id="imap_server"
                  type="text"
                  value={formData.imap_server}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      imap_server: e.target.value,
                    })
                  }
                  disabled={formData.provider !== "custom"}
                  required
                />
              </div>

              {/* IMAP Port */}
              <div className="space-y-2">
                <Label htmlFor="imap_port">IMAP Port</Label>
                <Input
                  id="imap_port"
                  type="number"
                  value={formData.imap_port}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      imap_port: parseInt(e.target.value),
                    })
                  }
                  required
                />
              </div>

              {/* Folder to Watch */}
              <div className="space-y-2">
                <Label htmlFor="folder">Folder to Watch</Label>
                <Input
                  id="folder"
                  type="text"
                  value={formData.folder_to_watch}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      folder_to_watch: e.target.value,
                    })
                  }
                  placeholder="INBOX"
                />
              </div>

              {/* Polling Interval */}
              <div className="space-y-2">
                <Label htmlFor="interval">Polling Interval (minutes)</Label>
                <Input
                  id="interval"
                  type="number"
                  min="1"
                  max="60"
                  value={formData.polling_interval_minutes}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      polling_interval_minutes: parseInt(e.target.value),
                    })
                  }
                />
              </div>
            </div>

            {/* Checkboxes */}
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="use_ssl"
                  checked={formData.use_ssl}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      use_ssl: e.target.checked,
                    })
                  }
                  className="h-4 w-4"
                />
                <Label htmlFor="use_ssl" className="font-normal">
                  Use SSL/TLS (Recommended)
                </Label>
              </div>

              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="mark_as_read"
                  checked={formData.mark_as_read}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      mark_as_read: e.target.checked,
                    })
                  }
                  className="h-4 w-4"
                />
                <Label htmlFor="mark_as_read" className="font-normal">
                  Mark emails as read after processing
                </Label>
              </div>

              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="polling_enabled"
                  checked={formData.polling_enabled}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      polling_enabled: e.target.checked,
                    })
                  }
                  className="h-4 w-4"
                />
                <Label htmlFor="polling_enabled" className="font-normal">
                  Enable automatic polling
                </Label>
              </div>
            </div>
          </details>

          {/* Test Connection Result */}
          {testResult && (
            <div
              className={`flex items-center gap-2 p-3 rounded-lg ${
                testResult.success
                  ? "bg-green-50 text-green-700 border border-green-200"
                  : "bg-red-50 text-red-700 border border-red-200"
              }`}
            >
              {testResult.success ? (
                <CheckCircle2 className="h-5 w-5" />
              ) : (
                <XCircle className="h-5 w-5" />
              )}
              <span className="text-sm">{testResult.message}</span>
            </div>
          )}

          <DialogFooter className="flex-col sm:flex-row gap-2">
            {/* Only show Test Connection for IMAP or non-Gmail */}
            {(!isGmailEmail || authMethod === "imap") && (
              <Button
                type="button"
                variant="outline"
                onClick={handleTestConnection}
                disabled={
                  testingConnection ||
                  !formData.email_address ||
                  !formData.imap_password
                }
                className="w-full sm:w-auto"
              >
                {testingConnection ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Testing...
                  </>
                ) : (
                  "Test Connection"
                )}
              </Button>
            )}
            <Button
              type="submit"
              disabled={
                loading ||
                (!testPassed && !existingConfig) ||
                (isGmailEmail &&
                  authMethod === "oauth" &&
                  !isGmailOAuthConnected)
              }
              className="w-full sm:w-auto"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : existingConfig ? (
                "Update Configuration"
              ) : (
                "Save Configuration"
              )}
            </Button>
          </DialogFooter>
          {!testPassed && !existingConfig && (
            <p className="text-xs text-orange-600 dark:text-orange-400 text-center mt-2">
              ⚠️{" "}
              {isGmailEmail && authMethod === "oauth"
                ? "Please connect with Google OAuth before saving"
                : "Please test the connection before saving"}
            </p>
          )}
        </form>
      </DialogContent>
    </Dialog>
  );
}