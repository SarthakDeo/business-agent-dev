"use client";

import { useState, useEffect } from "react";
import {
  Lock,
  X,
  Eye,
  EyeOff,
  ShieldCheck,
  Loader2,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Database,
  MessageSquare,
  Mail,
  Sparkles,
} from "lucide-react";
import { IntegrationStatus } from "@/lib/types";
import { api } from "@/lib/api";
import { getIntegrationMetadata, formatAgentErrorMessage } from "@/lib/utils";

interface IntegrationConnectDialogProps {
  integration: IntegrationStatus;
  onClose: () => void;
  onConnect: (secret: string, accountIdentifier?: string) => Promise<void>;
  loading?: boolean;
}

export function IntegrationConnectDialog({
  integration,
  onClose,
  onConnect,
  loading = false,
}: IntegrationConnectDialogProps) {
  const [secret, setSecret] = useState("");
  const [accountIdentifier, setAccountIdentifier] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Gmail OAuth specific states
  const [oauthLoading, setOauthLoading] = useState(false);
  const [showManualOAuth, setShowManualOAuth] = useState(false);

  const meta = getIntegrationMetadata(integration.integration);
  const isGmail = integration.integration.toLowerCase() === "gmail";
  const isSlack = integration.integration.toLowerCase() === "slack";
  const isCrm = integration.integration.toLowerCase() === "crm";

  // Listen for OAuth completion messages from popup window
  useEffect(() => {
    if (!isGmail) return;

    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === "OAUTH_COMPLETE" && event.data?.integration === "gmail") {
        setOauthLoading(false);
        onClose();
        // Trigger a page refresh/state reload
        window.location.reload();
      } else if (event.data?.type === "OAUTH_ERROR") {
        setOauthLoading(false);
        setError(event.data?.error || "Google authorization failed.");
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [isGmail, onClose]);

  const handleGoogleSignIn = async () => {
    setError(null);
    setOauthLoading(true);
    try {
      const data = await api.getGmailOAuthUrl();
      if (!data.url) {
        throw new Error("No authorization URL returned from server.");
      }

      // Open popup window centered on screen
      const width = 550;
      const height = 650;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;
      const popup = window.open(
        data.url,
        "voice2flow_google_oauth",
        `width=${width},height=${height},left=${left},top=${top},status=no,menubar=no,toolbar=no`
      );

      if (!popup || popup.closed) {
        // Fallback: direct redirect if popup blocked
        window.location.href = data.url;
        return;
      }

      // Check for popup closure
      const timer = setInterval(() => {
        if (popup.closed) {
          clearInterval(timer);
          setOauthLoading(false);
        }
      }, 1000);
    } catch (err: unknown) {
      setOauthLoading(false);
      setError(formatAgentErrorMessage(err));
    }
  };

  const handleFillDemoCrm = () => {
    setSecret("demo-crm-api-key");
    setAccountIdentifier("Local Demo CRM");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!secret.trim() || loading) return;

    setError(null);
    try {
      await onConnect(secret.trim(), accountIdentifier.trim() || undefined);
      // Immediately scrub sensitive inputs
      setSecret("");
      setAccountIdentifier("");
      onClose();
    } catch (err: unknown) {
      setError(formatAgentErrorMessage(err));
    }
  };

  const handleClose = () => {
    setSecret("");
    setAccountIdentifier("");
    setError(null);
    onClose();
  };

  const renderServiceHeaderIcon = () => {
    if (isGmail) return <Mail className="h-5 w-5 text-rose-400" />;
    if (isSlack) return <MessageSquare className="h-5 w-5 text-emerald-400" />;
    if (isCrm) return <Database className="h-5 w-5 text-blue-400" />;
    return <Lock className="h-5 w-5 text-indigo-400" />;
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="connect-dialog-title"
      className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 w-full max-w-md shadow-2xl space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-slate-800 border border-slate-700/60 flex items-center justify-center">
              {renderServiceHeaderIcon()}
            </div>
            <div>
              <h3 id="connect-dialog-title" className="font-bold text-base text-white">
                Connect {integration.name}
              </h3>
              <span className="text-[11px] text-indigo-400 font-mono">
                {meta.authTypeLabel}
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={handleClose}
            disabled={loading || oauthLoading}
            aria-label="Close modal"
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Security / Architecture callout */}
        <div className="p-3 rounded-xl bg-indigo-950/40 border border-indigo-900/60 flex items-start gap-2.5 text-xs text-indigo-200 leading-relaxed">
          <ShieldCheck className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
          <span>{meta.secretHelp}</span>
        </div>

        {/* Error message */}
        {error && (
          <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-900 text-xs text-rose-300 flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        {/* ─── GMAIL OAUTH FLOW ─── */}
        {isGmail && !showManualOAuth ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-center space-y-3">
              <p className="text-xs text-slate-300 leading-relaxed">
                Connect your Google Account to enable Voice2Flow to draft, search, and send emails through n8n workflows.
              </p>

              <button
                type="button"
                onClick={handleGoogleSignIn}
                disabled={oauthLoading || loading}
                className="w-full inline-flex items-center justify-center gap-2.5 px-4 py-2.5 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-semibold text-xs transition-all shadow-md active:scale-[0.99] disabled:opacity-50"
              >
                {oauthLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin text-slate-900" />
                ) : (
                  <svg className="h-4 w-4" viewBox="0 0 24 24">
                    <path
                      fill="#4285F4"
                      d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17Z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.33 24 12 24Z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.16 0 9.94 0 12s.45 3.84 1.25 5.42l4.03-3.15Z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98Z"
                    />
                  </svg>
                )}
                <span>{oauthLoading ? "Connecting to Google..." : "Connect with Google"}</span>
              </button>
            </div>

            <div className="text-center pt-1">
              <button
                type="button"
                onClick={() => setShowManualOAuth(true)}
                className="text-[11px] text-slate-500 hover:text-slate-300 underline underline-offset-2 transition-colors"
              >
                Or enter tokens / credentials manually
              </button>
            </div>
          </div>
        ) : (
          /* ─── STANDARD FORM (SLACK, CRM, OR MANUAL GMAIL) ─── */
          <form onSubmit={handleSubmit} className="space-y-4">
            {isCrm && (
              <div className="flex items-center justify-between bg-blue-950/30 border border-blue-900/50 rounded-xl p-2.5">
                <span className="text-[11px] text-blue-300">
                  Built-in Demo CRM (Fast setup)
                </span>
                <button
                  type="button"
                  onClick={handleFillDemoCrm}
                  className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-400 hover:text-blue-300 bg-blue-900/40 hover:bg-blue-900/70 border border-blue-800/80 px-2.5 py-1 rounded-lg transition-colors"
                >
                  <Sparkles className="h-3 w-3" />
                  Use Demo Key
                </button>
              </div>
            )}

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1.5">
                {isSlack
                  ? "Bot User OAuth Token (xoxb-...)"
                  : isCrm
                  ? "CRM API Key / Service Token"
                  : isGmail
                  ? "Google OAuth Tokens JSON / Access Token"
                  : `${meta.authTypeLabel} Secret`}{" "}
                <span className="text-rose-400">*</span>
              </label>
              <div className="relative">
                <input
                  type={showSecret ? "text" : "password"}
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  placeholder={meta.secretPlaceholder}
                  autoFocus
                  disabled={loading}
                  autoComplete="off"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-3.5 pr-10 py-2.5 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 font-mono transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowSecret(!showSecret)}
                  tabIndex={-1}
                  aria-label={showSecret ? "Hide secret" : "Show secret"}
                  className="absolute right-3 top-2.5 text-slate-500 hover:text-slate-300"
                >
                  {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <span className="text-[10px] text-slate-500 mt-1 block">
                {isSlack
                  ? "Starts with xoxb-. Requires chat:write and channels:read scopes."
                  : isCrm
                  ? "Maps to n8n's httpHeaderAuth with header X-API-Key."
                  : "Credential is held in memory and never displayed in the browser."}
              </span>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1.5">
                {isSlack
                  ? "Slack Workspace / Channel Label"
                  : "Account Identifier / Label"}{" "}
                <span className="text-slate-500 font-normal">(Optional)</span>
              </label>
              <input
                type="text"
                value={accountIdentifier}
                onChange={(e) => setAccountIdentifier(e.target.value)}
                placeholder={
                  isSlack
                    ? "e.g. Logistics Team (#logistics)"
                    : isCrm
                    ? "e.g. Local Demo CRM"
                    : "e.g. sales@voice2flow.ai"
                }
                disabled={loading}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 transition-colors"
              />
              <span className="text-[10px] text-slate-500 mt-1 block">
                A human-readable label shown on your dashboard and audit events.
              </span>
            </div>

            {isGmail && showManualOAuth && (
              <div className="text-center pt-1">
                <button
                  type="button"
                  onClick={() => setShowManualOAuth(false)}
                  className="text-[11px] text-slate-500 hover:text-slate-300 underline underline-offset-2 transition-colors"
                >
                  Back to Sign in with Google
                </button>
              </div>
            )}

            <div className="flex items-center gap-3 justify-end pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={handleClose}
                disabled={loading}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!secret.trim() || loading}
                className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold shadow-md shadow-indigo-600/30 transition-all"
              >
                {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                <span>{loading ? "Connecting..." : "Save Connection"}</span>
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
