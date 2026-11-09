"use client";

import { X, PlayCircle, Clock, Timer, User, Workflow, AlertCircle, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { ExecutionRecord } from "@/lib/types";
import { ExecutionStatusBadge } from "./execution-status";
import { formatDuration, formatRelativeTime, formatAgentErrorMessage, sanitizeParameters } from "@/lib/utils";

interface ExecutionDetailModalProps {
  execution: ExecutionRecord;
  onClose: () => void;
}

export function ExecutionDetailModal({ execution, onClose }: ExecutionDetailModalProps) {
  const duration = formatDuration(execution.started_at, execution.completed_at);
  const isFailed = (execution.status || "").toLowerCase() === "error" || (execution.status || "").toLowerCase() === "failed";
  const sanitizedMeta = sanitizeParameters(execution.metadata);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="execution-dialog-title"
      className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 w-full max-w-lg shadow-2xl space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-slate-800 border border-slate-700/60 flex items-center justify-center text-blue-400">
              <PlayCircle className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 id="execution-dialog-title" className="font-bold text-sm text-white font-mono">
                  {execution.id}
                </h3>
                <ExecutionStatusBadge status={execution.status} />
              </div>
              <span className="text-[11px] text-slate-400">
                Mode: <strong className="text-indigo-400">{execution.mode}</strong>
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Execution Metrics Grid */}
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-xl bg-slate-950/80 border border-slate-800/80 p-3 space-y-1">
            <span className="text-slate-400 flex items-center gap-1.5 text-[11px]">
              <Timer className="h-3 w-3 text-slate-500" />
              Duration
            </span>
            <span className="font-mono text-slate-200 font-semibold">{duration}</span>
          </div>

          <div className="rounded-xl bg-slate-950/80 border border-slate-800/80 p-3 space-y-1">
            <span className="text-slate-400 flex items-center gap-1.5 text-[11px]">
              <Clock className="h-3 w-3 text-slate-500" />
              Started
            </span>
            <span className="text-slate-200" title={execution.started_at}>
              {formatRelativeTime(execution.started_at)}
            </span>
          </div>

          <div className="rounded-xl bg-slate-950/80 border border-slate-800/80 p-3 space-y-1">
            <span className="text-slate-400 flex items-center gap-1.5 text-[11px]">
              <User className="h-3 w-3 text-slate-500" />
              Initiated By
            </span>
            <span className="font-mono text-slate-300 truncate block">
              {execution.user_id || "System / Agent"}
            </span>
          </div>

          <div className="rounded-xl bg-slate-950/80 border border-slate-800/80 p-3 space-y-1">
            <span className="text-slate-400 flex items-center gap-1.5 text-[11px]">
              <Workflow className="h-3 w-3 text-slate-500" />
              Automation Link
            </span>
            {execution.automation_id ? (
              <Link
                href={`/automations/${execution.automation_id}`}
                className="font-mono text-indigo-400 hover:underline truncate block"
              >
                {execution.automation_id}
              </Link>
            ) : (
              <span className="text-slate-500 font-mono">None (Direct)</span>
            )}
          </div>
        </div>

        {/* Safe Error Details */}
        {isFailed && (
          <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-900/60 text-xs text-rose-200 space-y-1.5">
            <div className="flex items-center gap-2 font-semibold text-rose-300">
              <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
              <span>Execution Error ({execution.error_code || "EXECUTION_FAILED"})</span>
            </div>
            <p className="text-rose-200/90 leading-relaxed pl-6">
              {formatAgentErrorMessage(null, execution.error_code)}
            </p>
          </div>
        )}

        {/* Safe Execution Metadata (sanitized, no raw secrets) */}
        {sanitizedMeta && Object.keys(sanitizedMeta).length > 0 && (
          <div className="rounded-xl bg-slate-950/70 border border-slate-800 p-3.5 space-y-2 text-xs">
            <div className="flex items-center gap-1.5 text-slate-300 font-semibold text-[11px]">
              <ShieldCheck className="h-3.5 w-3.5 text-indigo-400" />
              <span>Safe Execution Context</span>
            </div>
            <div className="space-y-1 font-mono text-[11px]">
              {Object.entries(sanitizedMeta).map(([k, v]) => (
                <div key={k} className="flex justify-between items-center py-0.5 border-b border-slate-800/40 last:border-0">
                  <span className="text-slate-400">{k}:</span>
                  <span className="text-slate-200 truncate max-w-[220px]">
                    {typeof v === "object" ? JSON.stringify(v) : String(v)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-end pt-3 border-t border-slate-800">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
