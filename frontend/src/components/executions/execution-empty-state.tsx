"use client";

import { PlayCircle, RefreshCw } from "lucide-react";

interface ExecutionEmptyStateProps {
  title?: string;
  description?: string;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function ExecutionEmptyState({
  title = "No executions yet",
  description = "Completed and failed workflow executions will appear here.",
  onRefresh,
  isRefreshing = false,
}: ExecutionEmptyStateProps) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-12 text-center flex flex-col items-center justify-center space-y-4">
      <div className="h-12 w-12 rounded-2xl bg-slate-800/80 border border-slate-700/60 flex items-center justify-center text-slate-400">
        <PlayCircle className="h-6 w-6 text-slate-500" />
      </div>
      <div className="space-y-1 max-w-sm">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <p className="text-xs text-slate-400 leading-relaxed">{description}</p>
      </div>
      {onRefresh && (
        <button
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
          <span>Refresh Executions</span>
        </button>
      )}
    </div>
  );
}
