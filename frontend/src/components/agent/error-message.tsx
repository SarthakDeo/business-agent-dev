"use client";

import { AlertCircle, RefreshCw, X } from "lucide-react";
import { formatAgentErrorMessage } from "@/lib/utils";

interface ErrorMessageProps {
  error: unknown;
  errorCode?: string | null;
  onRetry?: () => void;
  onDismiss?: () => void;
}

export function ErrorMessage({
  error,
  errorCode,
  onRetry,
  onDismiss,
}: ErrorMessageProps) {
  const message = formatAgentErrorMessage(error, errorCode);

  return (
    <div
      role="alert"
      className="p-3.5 rounded-xl bg-rose-950/60 border border-rose-800/60 text-rose-200 flex items-start justify-between gap-3 shadow-md animate-in fade-in duration-200"
    >
      <div className="flex items-start gap-2.5">
        <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
        <div>
          <div className="text-xs font-bold text-rose-300 uppercase tracking-wider mb-0.5">
            {errorCode || "Operation Failed"}
          </div>
          <div className="text-xs text-rose-200/90 leading-relaxed font-sans">
            {message}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="flex items-center gap-1 text-[11px] font-semibold text-rose-300 hover:text-white px-2 py-1 rounded bg-rose-900/50 hover:bg-rose-900/80 transition-colors"
          >
            <RefreshCw className="h-3 w-3" />
            <span>Retry</span>
          </button>
        )}
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss error"
            className="text-rose-400 hover:text-white p-1 rounded transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
