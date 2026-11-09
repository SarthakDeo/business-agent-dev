"use client";

import Link from "next/link";
import { Workflow, Plus, Sparkles, Bot } from "lucide-react";

interface AutomationEmptyStateProps {
  filtered?: boolean;
  onClearFilters?: () => void;
}

export function AutomationEmptyState({
  filtered = false,
  onClearFilters,
}: AutomationEmptyStateProps) {
  if (filtered) {
    return (
      <div className="p-12 text-center rounded-2xl bg-slate-900/50 border border-slate-800 space-y-3">
        <Workflow className="h-10 w-10 text-slate-600 mx-auto" />
        <h3 className="font-semibold text-slate-200">No matching automations</h3>
        <p className="text-xs text-slate-400 max-w-sm mx-auto">
          No automations matched your search criteria or status filter.
        </p>
        {onClearFilters && (
          <button
            onClick={onClearFilters}
            className="mt-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 transition-colors"
          >
            Clear Filters
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="p-10 sm:p-14 text-center rounded-2xl bg-slate-900/60 border border-slate-800 shadow-md space-y-5 max-w-2xl mx-auto">
      <div className="h-16 w-16 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 mx-auto shadow-lg shadow-indigo-950/30">
        <Workflow className="h-8 w-8" />
      </div>

      <div>
        <h3 className="text-lg font-bold text-white tracking-tight">
          No automations yet
        </h3>
        <p className="text-sm text-slate-400 max-w-md mx-auto mt-1.5 leading-relaxed">
          Tell Voice2Flow what you want to automate in plain English, and it compiles, tests, and deploys autonomous n8n workflows for you.
        </p>
      </div>

      <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
        <Link
          href="/agent?prompt=Create an automation for new website complaints"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-lg shadow-indigo-600/30 transition-all hover:scale-105"
        >
          <Sparkles className="h-4 w-4" />
          <span>Build First Automation</span>
        </Link>

        <Link
          href="/agent"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs border border-slate-700 transition-colors"
        >
          <Bot className="h-4 w-4" />
          <span>Open Voice2Flow Agent</span>
        </Link>
      </div>
    </div>
  );
}
