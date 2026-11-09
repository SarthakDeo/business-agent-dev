"use client";

import { useState, useMemo } from "react";
import {
  ShieldCheck,
  RefreshCw,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
} from "lucide-react";
import { useActivity } from "@/lib/hooks";
import { getSafeEventSummary } from "@/lib/utils";
import { ActivityList } from "@/components/activity/activity-list";
import { ActivityFilters, ActivityFilterType } from "@/components/activity/activity-filters";

const PAGE_SIZE = 25;

export default function ActivityPage() {
  const [page, setPage] = useState(0);
  const [activeTab, setActiveTab] = useState<ActivityFilterType>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const offset = page * PAGE_SIZE;

  const {
    data: events,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useActivity(PAGE_SIZE, offset);

  // Filter items client-side on safe display fields
  const filteredEvents = useMemo(() => {
    if (!events) return [];

    return events.filter((e) => {
      const normType = (e.event_type || "").toUpperCase();

      // Tab filtering
      if (activeTab === "requests" && normType !== "AGENT_REQUEST") return false;
      if (activeTab === "plans" && normType !== "PLAN_CREATED") return false;
      if (activeTab === "automations" && !normType.startsWith("AUTOMATION_")) return false;
      if (activeTab === "executions" && !normType.startsWith("EXECUTION_")) return false;

      // Search query filtering
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const summary = getSafeEventSummary(e.event_type, e.mode, e.status, e.metadata).toLowerCase();
        const matches =
          e.event_type.toLowerCase().includes(q) ||
          (e.mode && e.mode.toLowerCase().includes(q)) ||
          (e.status && e.status.toLowerCase().includes(q)) ||
          (e.run_id && e.run_id.toLowerCase().includes(q)) ||
          (e.user_id && e.user_id.toLowerCase().includes(q)) ||
          summary.includes(q);

        if (!matches) return false;
      }

      return true;
    });
  }, [events, activeTab, searchQuery]);

  const hasNextPage = Boolean(events && events.length === PAGE_SIZE);
  const hasPrevPage = page > 0;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-xl font-bold text-white">Audit & Activity Trail</h2>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-950/70 text-indigo-300 border border-indigo-800/60">
              <ShieldCheck className="h-3 w-3 text-indigo-400" />
              Audited Stream
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl">
            Tamper-evident audit log stream persisted in PostgreSQL. Tracks all autonomous agent interactions, planning events, and execution dispatches.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition-colors disabled:opacity-50"
            title="Refresh audit stream"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin text-indigo-400" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Security Architecture Callout */}
      <div className="rounded-2xl bg-indigo-950/20 border border-indigo-900/40 p-4 flex items-start gap-3 text-xs text-indigo-200">
        <ShieldAlert className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-semibold text-indigo-300 block">
            Read-Only Audit Isolation
          </span>
          <p className="text-indigo-200/80 leading-relaxed">
            Audit events are immutable records written exclusively by the backend during agent operations. Sensitive keys, authorization tokens, and credentials are automatically redacted before durable storage.
          </p>
        </div>
      </div>

      {/* Filter and Search Controls */}
      <ActivityFilters
        activeTab={activeTab}
        onTabChange={(tab) => {
          setActiveTab(tab);
          setPage(0);
        }}
        searchQuery={searchQuery}
        onSearchChange={(q) => {
          setSearchQuery(q);
          setPage(0);
        }}
      />

      {/* Content Stream */}
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
                <div className="h-3 w-16 bg-slate-800 rounded" />
              </div>
              <div className="h-3 w-3/4 bg-slate-800/70 rounded ml-11" />
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-2xl border border-rose-900/60 bg-rose-950/20 p-8 text-center space-y-3">
          <AlertCircle className="h-8 w-8 text-rose-400 mx-auto" />
          <h3 className="text-sm font-semibold text-white">Failed to load activity</h3>
          <p className="text-xs text-rose-300/80 max-w-md mx-auto">
            {error instanceof Error ? error.message : "An error occurred while loading audit events."}
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold border border-slate-700 transition-colors"
          >
            Retry Loading
          </button>
        </div>
      ) : (
        <ActivityList
          events={filteredEvents}
          searchQuery={searchQuery}
          onRefresh={() => refetch()}
          isRefreshing={isFetching}
        />
      )}

      {/* Pagination Controls */}
      {!isLoading && !isError && (events?.length || 0) > 0 && (
        <div className="flex items-center justify-between pt-4 border-t border-slate-800/80 text-xs text-slate-400">
          <span>
            Showing page {page + 1} ({filteredEvents.length} items on page)
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
    </div>
  );
}
