"use client";

import { Search, X } from "lucide-react";

export type ActivityFilterType = "all" | "requests" | "plans" | "automations" | "executions";

interface ActivityFiltersProps {
  activeTab: ActivityFilterType;
  onTabChange: (tab: ActivityFilterType) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export function ActivityFilters({
  activeTab,
  onTabChange,
  searchQuery,
  onSearchChange,
}: ActivityFiltersProps) {
  const tabs: Array<{ id: ActivityFilterType; label: string }> = [
    { id: "all", label: "All Activity" },
    { id: "requests", label: "Requests" },
    { id: "plans", label: "Plans" },
    { id: "automations", label: "Automations" },
    { id: "executions", label: "Executions" },
  ];

  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
      {/* Category Tabs */}
      <div className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-xl border border-slate-800 self-start">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onTabChange(tab.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === tab.id
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search Input */}
      <div className="relative w-full md:w-64">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search activity..."
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
