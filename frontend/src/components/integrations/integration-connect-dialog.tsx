"use client";

import { useState } from "react";
import { Lock, Key, X, Eye, EyeOff, ShieldCheck, Loader2 } from "lucide-react";
import { IntegrationStatus } from "@/lib/types";
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

  const meta = getIntegrationMetadata(integration.integration);

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
    // Scrub secret state on cancel
    setSecret("");
    setAccountIdentifier("");
    setError(null);
    onClose();
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
            <div className="h-10 w-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Lock className="h-5 w-5" />
            </div>
            <div>
              <h3 id="connect-dialog-title" className="font-bold text-base text-white">
                Connect {integration.name}
              </h3>
              <span className="text-[11px] text-indigo-400 font-mono">
                Auth Type: {meta.authTypeLabel}
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={handleClose}
            disabled={loading}
            aria-label="Close modal"
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Security callout */}
        <div className="p-3 rounded-xl bg-indigo-950/40 border border-indigo-900/60 flex items-start gap-2.5 text-xs text-indigo-200 leading-relaxed">
          <ShieldCheck className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
          <span>
            {meta.secretHelp}
          </span>
        </div>

        {/* Error message */}
        {error && (
          <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-900 text-xs text-rose-300">
            {error}
          </div>
        )}

        {/* Connect Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1.5">
              {meta.authTypeLabel} Secret / Key <span className="text-rose-400">*</span>
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
              This credential is held in memory and will never be displayed in the browser.
            </span>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1.5">
              Account Identifier / Label <span className="text-slate-500 font-normal">(Optional)</span>
            </label>
            <input
              type="text"
              value={accountIdentifier}
              onChange={(e) => setAccountIdentifier(e.target.value)}
              placeholder="e.g. sales@voice2flow.ai or Acme Workspace"
              disabled={loading}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 transition-colors"
            />
            <span className="text-[10px] text-slate-500 mt-1 block">
              A human-readable label shown on your dashboard and audit events.
            </span>
          </div>

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
      </div>
    </div>
  );
}
