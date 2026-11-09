"use client";

import Link from "next/link";
import { Workflow, ChevronRight, Clock, Hash, Layers } from "lucide-react";
import { AutomationSummary } from "@/lib/types";
import { AutomationStatusBadge } from "./automation-status";
import { formatRelativeTime } from "@/lib/utils";

interface AutomationCardProps {
  automation: AutomationSummary;
}

export function AutomationCard({ automation }: AutomationCardProps) {
  return (
    <Link
      href={`/automations/${automation.id}`}
      className="group block rounded-2xl bg-slate-900 border border-slate-800 p-5 hover:border-indigo-500/50 hover:bg-slate-900/90 hover:shadow-lg hover:shadow-indigo-950/20 transition-all text-left"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-10 w-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 group-hover:scale-105 transition-transform shrink-0">
            <Workflow className="h-5 w-5" />
          </div>

          <div className="min-w-0">
            <h3 className="font-bold text-base text-white group-hover:text-indigo-300 transition-colors truncate">
              {automation.name}
            </h3>
            <div className="flex items-center gap-2 text-[11px] font-mono text-slate-500 mt-0.5">
              <Hash className="h-3 w-3 shrink-0" />
              <span className="truncate">{automation.id}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-center shrink-0">
          <AutomationStatusBadge status={automation.status} size="sm" />
          <div className="h-8 w-8 rounded-lg bg-slate-800/60 border border-slate-700/60 flex items-center justify-center text-slate-400 group-hover:text-white group-hover:bg-indigo-600 transition-colors">
            <ChevronRight className="h-4 w-4" />
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
        <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
          <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider block mb-0.5">
            Steps
          </span>
          <div className="flex items-center gap-1.5 text-slate-200 font-semibold">
            <Layers className="h-3.5 w-3.5 text-indigo-400" />
            <span>
              {automation.step_count} {automation.step_count === 1 ? "step" : "steps"}
            </span>
          </div>
        </div>

        <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
          <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider block mb-0.5">
            n8n Workflow
          </span>
          <div className="font-mono text-slate-300 truncate text-[11px]">
            {automation.n8n_workflow_id}
          </div>
        </div>

        <div className="col-span-2 sm:col-span-1 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
          <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider block mb-0.5">
            Updated
          </span>
          <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
            <Clock className="h-3 w-3 text-slate-500" />
            <span>{formatRelativeTime(automation.updated_at)}</span>
          </div>
        </div>
      </div>
    </Link>
  );
}
