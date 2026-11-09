"use client";

import Link from "next/link";
import { PlayCircle, Clock, Timer, Workflow, Eye, AlertCircle } from "lucide-react";
import { ExecutionRecord } from "@/lib/types";
import { ExecutionStatusBadge } from "./execution-status";
import { formatDuration, formatRelativeTime, formatAgentErrorMessage } from "@/lib/utils";

interface ExecutionRowProps {
  execution: ExecutionRecord;
  onInspect: (execution: ExecutionRecord) => void;
}

export function ExecutionRow({ execution, onInspect }: ExecutionRowProps) {
  const duration = formatDuration(execution.started_at, execution.completed_at);
  const isFailed = (execution.status || "").toLowerCase() === "error" || (execution.status || "").toLowerCase() === "failed";

  const getModeBadgeClass = (mode?: string | null) => {
    switch ((mode || "").toUpperCase()) {
      case "ASK":
        return "bg-blue-950/60 text-blue-400 border-blue-800/50";
      case "DO":
        return "bg-amber-950/60 text-amber-400 border-amber-800/50";
      case "AUTOMATE":
        return "bg-purple-950/60 text-purple-400 border-purple-800/50";
      default:
        return "bg-slate-800 text-slate-400 border-slate-700";
    }
  };

  return (
    <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4 hover:border-slate-700/80 transition-all duration-200 shadow-sm space-y-3">
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-xl bg-slate-800/80 border border-slate-700/50 flex items-center justify-center shrink-0 text-blue-400">
            <PlayCircle className="h-4 w-4" />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold text-white truncate max-w-[150px] sm:max-w-xs" title={execution.id}>
              {execution.id}
            </span>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${getModeBadgeClass(execution.mode)}`}>
              {execution.mode}
            </span>
            <ExecutionStatusBadge status={execution.status} />
          </div>
        </div>

        {/* Action Button */}
        <button
          type="button"
          onClick={() => onInspect(execution)}
          className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg border border-slate-700 transition-colors self-start sm:self-auto"
        >
          <Eye className="h-3 w-3 text-indigo-400" />
          <span>Details</span>
        </button>
      </div>

      {/* Details Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs pt-1 border-t border-slate-800/50">
        <div>
          <span className="text-slate-400 block text-[10px] uppercase font-semibold">Duration</span>
          <span className="text-slate-200 font-mono flex items-center gap-1 mt-0.5">
            <Timer className="h-3 w-3 text-slate-500" />
            {duration}
          </span>
        </div>

        <div>
          <span className="text-slate-400 block text-[10px] uppercase font-semibold">Started</span>
          <span className="text-slate-200 flex items-center gap-1 mt-0.5" title={execution.started_at}>
            <Clock className="h-3 w-3 text-slate-500" />
            {formatRelativeTime(execution.started_at)}
          </span>
        </div>

        <div>
          <span className="text-slate-400 block text-[10px] uppercase font-semibold">Automation</span>
          {execution.automation_id ? (
            <Link
              href={`/automations/${execution.automation_id}`}
              className="font-mono text-indigo-400 hover:underline flex items-center gap-1 mt-0.5 truncate"
            >
              <Workflow className="h-3 w-3 shrink-0" />
              <span className="truncate">{execution.automation_id}</span>
            </Link>
          ) : (
            <span className="text-slate-500 font-mono mt-0.5 block">—</span>
          )}
        </div>

        <div>
          <span className="text-slate-400 block text-[10px] uppercase font-semibold">Initiated By</span>
          <span className="text-slate-300 font-mono mt-0.5 truncate block">
            {execution.user_id || "System"}
          </span>
        </div>
      </div>

      {/* Safe Error Banner if Failed */}
      {isFailed && (
        <div className="p-2.5 rounded-xl bg-rose-950/40 border border-rose-900/50 flex items-center gap-2 text-xs text-rose-300">
          <AlertCircle className="h-3.5 w-3.5 text-rose-400 shrink-0" />
          <span className="truncate">
            {formatAgentErrorMessage(null, execution.error_code)}
          </span>
        </div>
      )}
    </div>
  );
}
