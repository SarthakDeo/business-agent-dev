"use client";

import { useState } from "react";
import { AlertTriangle, X, Loader2, Unplug } from "lucide-react";
import { IntegrationStatus } from "@/lib/types";
import { formatAgentErrorMessage } from "@/lib/utils";

interface IntegrationDisconnectDialogProps {
  integration: IntegrationStatus;
  onClose: () => void;
  onDisconnect: () => Promise<void>;
  loading?: boolean;
}

export function IntegrationDisconnectDialog({
  integration,
  onClose,
  onDisconnect,
  loading = false,
}: IntegrationDisconnectDialogProps) {
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async () => {
    if (loading) return;
    setError(null);
    try {
      await onDisconnect();
      onClose();
    } catch (err: unknown) {
      setError(formatAgentErrorMessage(err));
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="disconnect-dialog-title"
      className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 w-full max-w-md shadow-2xl space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-rose-600/20 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <h3 id="disconnect-dialog-title" className="font-bold text-base text-white">
                Disconnect {integration.name}
              </h3>
              <span className="text-[11px] text-slate-400">
                Revoke external service connection
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            aria-label="Close modal"
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Impact Warning */}
        <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-900/60 text-xs text-rose-200 leading-relaxed space-y-2">
          <p className="font-semibold text-rose-300">
            Are you sure you want to disconnect {integration.name}?
          </p>
          <p className="text-rose-200/90">
            Active automations that rely on {integration.name} will immediately lose access and may fail to execute until reconnected. Credentials stored in memory for this service will be flushed.
          </p>
        </div>

        {/* Account Details if present */}
        {integration.account_identifier && (
          <div className="rounded-xl bg-slate-950 border border-slate-800/80 p-3 text-xs space-y-1">
            <span className="text-slate-400 block text-[11px]">Connected Account:</span>
            <span className="font-mono text-slate-200 font-medium">
              {integration.account_identifier}
            </span>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-900 text-xs text-rose-300">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3 justify-end pt-3 border-t border-slate-800">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition-colors"
          >
            Keep Connected
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white text-xs font-semibold shadow-md shadow-rose-600/30 transition-all"
          >
            {loading ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Disconnecting...</span>
              </>
            ) : (
              <>
                <Unplug className="h-3.5 w-3.5" />
                <span>Disconnect Service</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
