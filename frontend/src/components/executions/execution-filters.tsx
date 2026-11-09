"use client";

import { Search, X } from "lucide-react";

export type ExecutionStatusFilter = "all" | "completed" | "failed" | "running";
export type ExecutionModeFilter = "all" | "ASK" | "DO" | "AUTOMATE";

interface ExecutionFiltersProps {
  statusFilter: ExecutionStatusFilter;
  onStatusChange: (status: ExecutionStatusFilter) => void;
  modeFilter: ExecutionModeFilter;
  onModeChange: (mode: ExecutionModeFilter) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export function ExecutionFilters({
  statusFilter,
  onStatusChange,
  modeFilter,
  onModeChange,
  searchQuery,
  onSearchChange,
}: ExecutionFiltersProps) {
  const statusTabs: Array<{ id: ExecutionStatusFilter; label: string }> = [
    { id: "all", label: "All Status" },
    { id: "completed", label: "Completed" },
    { id: "failed", label: "Failed" },
    { id: "running", label: "Running" },
  ];

  const modes: Array<{ id: ExecutionModeFilter; label: string }> = [
    { id: "all", label: "All Modes" },
    { id: "ASK", label: "ASK" },
    { id: "DO", label: "DO" },
    { id: "AUTOMATE", label: "AUTOMATE" },
  ];

  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
      {/* Filters Row */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Status Tabs */}
        <div className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
          {statusTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => onStatusChange(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                statusFilter === tab.id
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Mode Selector */}
        <div className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
          {modes.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => onModeChange(m.id)}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                modeFilter === m.id
                  ? "bg-slate-800 text-indigo-400 font-semibold"
                  : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/40"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Search Input */}
      <div className="relative w-full md:w-64">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search executions..."
          className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
        />
        <Search className="h-3.5 w-3.5 text-slate-500 absolute left-3 top-3 pointer-events-none" />
        {searchQuery && (
          <button
            type="button"
            onClick={() => onSearchChange("")}
            className="absolute right-3 top-2.5 text-xs text-slate-500 hover:text-slate-300"
            aria-label="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
