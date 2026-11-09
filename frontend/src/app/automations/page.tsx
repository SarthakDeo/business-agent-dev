"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { Workflow, Plus, RefreshCw, Sparkles, AlertCircle } from "lucide-react";
import { useAutomationsList } from "@/lib/hooks";
import { AutomationCard } from "@/components/automations/automation-card";
import { AutomationSearch } from "@/components/automations/automation-search";
import { AutomationEmptyState } from "@/components/automations/automation-empty-state";
import { ErrorMessage } from "@/components/agent/error-message";

export default function AutomationsPage() {
  const { data: automations, isLoading, error, refetch, isFetching } = useAutomationsList();

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  // Client-side filtering across name, ID, and status
  const filteredAutomations = useMemo(() => {
    if (!automations) return [];
    return automations.filter((a) => {
      // Status filter
      if (statusFilter === "active" && !["active", "created"].includes(a.status.toLowerCase())) {
        return false;
      }
      if (statusFilter === "updated" && a.status.toLowerCase() !== "updated") {
        return false;
      }
      if (statusFilter === "inactive" && ["active", "created", "updated"].includes(a.status.toLowerCase())) {
        return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesName = a.name.toLowerCase().includes(query);
        const matchesId = a.id.toLowerCase().includes(query);
        const matchesN8n = a.n8n_workflow_id.toLowerCase().includes(query);
        return matchesName || matchesId || matchesN8n;
      }

      return true;
    });
  }, [automations, searchQuery, statusFilter]);

  const hasAutomations = automations && automations.length > 0;
  const isFilteredEmpty = hasAutomations && filteredAutomations.length === 0;

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Top Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Workflow className="h-4 w-4" />
            </div>
            <h1 className="text-xl font-bold text-white tracking-tight">
              Automations
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Manage autonomous workflows compiled and deployed by Voice2Flow.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            title="Refresh automations list"
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-900 border border-slate-800 text-slate-300 rounded-xl text-xs hover:bg-slate-800 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>

          <Link
            href="/agent?prompt=Create an automation for "
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all hover:scale-105"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Create with Voice2Flow</span>
          </Link>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <ErrorMessage
          error={error}
          onRetry={() => refetch()}
        />
      )}

      {/* Loading Skeletons */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="h-44 rounded-2xl bg-slate-900/40 border border-slate-800/80 animate-pulse p-5 space-y-4"
            >
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-slate-800" />
                <div className="space-y-1.5 flex-1">
                  <div className="h-4 bg-slate-800 rounded w-3/4" />
                  <div className="h-3 bg-slate-800/60 rounded w-1/2" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 pt-2">
                <div className="h-12 bg-slate-800/40 rounded-lg" />
                <div className="h-12 bg-slate-800/40 rounded-lg" />
                <div className="h-12 bg-slate-800/40 rounded-lg" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Main Content Area */}
      {!isLoading && !error && (
        <>
          {hasAutomations && (
            <AutomationSearch
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              statusFilter={statusFilter}
              onStatusFilterChange={setStatusFilter}
              totalCount={automations.length}
              filteredCount={filteredAutomations.length}
            />
          )}

          {!hasAutomations ? (
            <AutomationEmptyState />
          ) : isFilteredEmpty ? (
            <AutomationEmptyState
              filtered
              onClearFilters={() => {
                setSearchQuery("");
                setStatusFilter("all");
              }}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredAutomations.map((automation) => (
                <AutomationCard key={automation.id} automation={automation} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
