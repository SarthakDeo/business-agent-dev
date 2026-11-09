"use client";

import { Search, X, Filter } from "lucide-react";
import { clsx } from "clsx";

interface AutomationSearchProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  statusFilter: string;
  onStatusFilterChange: (status: string) => void;
  totalCount: number;
  filteredCount: number;
}

export function AutomationSearch({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  totalCount,
  filteredCount,
}: AutomationSearchProps) {
  const filterOptions = [
    { id: "all", label: "All" },
    { id: "active", label: "Active" },
    { id: "updated", label: "Updated" },
    { id: "inactive", label: "Inactive" },
  ];

  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-2xl border border-slate-800">
      {/* Search Input */}
      <div className="relative flex-1">
        <Search className="absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search by name, workflow ID, tool..."
          className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-9 py-2 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => onSearchChange("")}
            className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200 p-0.5 rounded"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 self-start sm:self-center">
        {filterOptions.map((opt) => {
          const isActive = statusFilter === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => onStatusFilterChange(opt.id)}
              className={clsx(
                "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
                isActive
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-slate-950/70 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800"
              )}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
