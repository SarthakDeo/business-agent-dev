"use client";

import { useState, useMemo } from "react";
import {
  PlayCircle,
  RefreshCw,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Eye,
} from "lucide-react";
import { ExecutionRecord } from "@/lib/types";
import { useExecutions } from "@/lib/hooks";
import { ExecutionRow } from "@/components/executions/execution-row";
import { ExecutionFilters, ExecutionStatusFilter, ExecutionModeFilter } from "@/components/executions/execution-filters";
import { ExecutionEmptyState } from "@/components/executions/execution-empty-state";
import { ExecutionDetailModal } from "@/components/executions/execution-detail-modal";

const PAGE_SIZE = 25;

export default function ExecutionsPage() {
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState<ExecutionStatusFilter>("all");
  const [modeFilter, setModeFilter] = useState<ExecutionModeFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [inspectedExecution, setInspectedExecution] = useState<ExecutionRecord | null>(null);

  const offset = page * PAGE_SIZE;

  const {
    data: executions,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useExecutions(PAGE_SIZE, offset);

  // Filter items client-side on safe display fields
  const filteredExecutions = useMemo(() => {
    if (!executions) return [];

    return executions.filter((x) => {
      const normStatus = (x.status || "").toLowerCase();
      const normMode = (x.mode || "").toUpperCase();

      // Status filtering
      if (statusFilter === "completed" && !(normStatus === "completed" || normStatus === "success")) return false;
      if (statusFilter === "failed" && !(normStatus === "failed" || normStatus === "error")) return false;
      if (statusFilter === "running" && !(normStatus === "running" || normStatus === "in_progress")) return false;

      // Mode filtering
      if (modeFilter !== "all" && normMode !== modeFilter) return false;

      // Search query filtering
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matches =
          x.id.toLowerCase().includes(q) ||
          normMode.toLowerCase().includes(q) ||
          normStatus.toLowerCase().includes(q) ||
          (x.automation_id && x.automation_id.toLowerCase().includes(q)) ||
          (x.request_id && x.request_id.toLowerCase().includes(q)) ||
          (x.user_id && x.user_id.toLowerCase().includes(q)) ||
          (x.error_code && x.error_code.toLowerCase().includes(q));

        if (!matches) return false;
      }

      return true;
    });
  }, [executions, statusFilter, modeFilter, searchQuery]);

  const hasNextPage = Boolean(executions && executions.length === PAGE_SIZE);
  const hasPrevPage = page > 0;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-xl font-bold text-white">Execution History</h2>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-950/70 text-indigo-300 border border-indigo-800/60">
              <PlayCircle className="h-3 w-3 text-indigo-400" />
              Observability Records
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl">
            Monitor direct tool dispatches, autonomous DO actions, and orchestrated n8n automation runs.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition-colors disabled:opacity-50"
            title="Refresh execution history"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin text-indigo-400" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Observability Notice */}
      <div className="rounded-2xl bg-indigo-950/20 border border-indigo-900/40 p-4 flex items-start gap-3 text-xs text-indigo-200">
        <Eye className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-semibold text-indigo-300 block">
            Read-Only Observability
          </span>
          <p className="text-indigo-200/80 leading-relaxed">
            Execution history is an immutable telemetry log. Records document duration, step results, and safe error codes. Sensitive credentials and raw authentication tokens are never captured or rendered.
          </p>
        </div>
      </div>

      {/* Filters and Search */}
      <ExecutionFilters
        statusFilter={statusFilter}
        onStatusChange={(s) => {
          setStatusFilter(s);
          setPage(0);
        }}
        modeFilter={modeFilter}
        onModeChange={(m) => {
          setModeFilter(m);
          setPage(0);
        }}
        searchQuery={searchQuery}
        onSearchChange={(q) => {
          setSearchQuery(q);
          setPage(0);
        }}
      />

      {/* Content Area */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="rounded-2xl bg-slate-900/60 border border-slate-800 p-4 space-y-3 animate-pulse"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-xl bg-slate-800" />
                  <div className="h-4 w-32 bg-slate-800 rounded" />
                </div>
                <div className="h-5 w-20 rounded-full bg-slate-800" />
              </div>
              <div className="grid grid-cols-4 gap-2 pt-2 border-t border-slate-800/40">
                <div className="h-6 bg-slate-800/60 rounded" />
                <div className="h-6 bg-slate-800/60 rounded" />
                <div className="h-6 bg-slate-800/60 rounded" />
                <div className="h-6 bg-slate-800/60 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-2xl border border-rose-900/60 bg-rose-950/20 p-8 text-center space-y-3">
          <AlertCircle className="h-8 w-8 text-rose-400 mx-auto" />
          <h3 className="text-sm font-semibold text-white">Failed to load executions</h3>
          <p className="text-xs text-rose-300/80 max-w-md mx-auto">
            {error instanceof Error ? error.message : "An error occurred while loading execution records."}
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold border border-slate-700 transition-colors"
          >
            Retry Loading
          </button>
        </div>
      ) : filteredExecutions.length === 0 ? (
        <ExecutionEmptyState
          title={searchQuery || statusFilter !== "all" || modeFilter !== "all" ? "No matching executions" : "No executions yet"}
          description={
            searchQuery || statusFilter !== "all" || modeFilter !== "all"
              ? "No execution records match your current filter criteria."
              : "Completed and failed workflow executions will appear here."
          }
          onRefresh={() => refetch()}
          isRefreshing={isFetching}
        />
      ) : (
        <div className="space-y-3">
          {filteredExecutions.map((x) => (
            <ExecutionRow
              key={x.id}
              execution={x}
              onInspect={(selected) => setInspectedExecution(selected)}
            />
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      {!isLoading && !isError && (executions?.length || 0) > 0 && (
        <div className="flex items-center justify-between pt-4 border-t border-slate-800/80 text-xs text-slate-400">
          <span>
            Showing page {page + 1} ({filteredExecutions.length} items on page)
          </span>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={!hasPrevPage || isFetching}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-40 disabled:pointer-events-none transition-colors border border-slate-700"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Previous</span>
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasNextPage || isFetching}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-40 disabled:pointer-events-none transition-colors border border-slate-700"
            >
              <span>Next</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Detail Inspection Modal */}
      {inspectedExecution && (
        <ExecutionDetailModal
          execution={inspectedExecution}
          onClose={() => setInspectedExecution(null)}
        />
      )}
    </div>
  );
}
