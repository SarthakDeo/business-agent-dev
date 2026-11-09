"use client";

import { CheckCircle2, AlertCircle, Loader2, PlayCircle } from "lucide-react";

interface ExecutionStatusBadgeProps {
  status: string;
  size?: "xs" | "sm";
}

export function ExecutionStatusBadge({ status, size = "xs" }: ExecutionStatusBadgeProps) {
  const norm = (status || "").toLowerCase();

  const isCompleted = norm === "completed" || norm === "success";
  const isFailed = norm === "failed" || norm === "error";
  const isRunning = norm === "running" || norm === "in_progress";

  const sizeClasses = size === "xs" ? "text-[10px] px-2 py-0.5 gap-1" : "text-xs px-2.5 py-1 gap-1.5";

  if (isCompleted) {
    return (
      <span
        className={`inline-flex items-center font-bold uppercase tracking-wider rounded-full border bg-emerald-950/60 text-emerald-400 border-emerald-800/50 shadow-sm ${sizeClasses}`}
      >
        <CheckCircle2 className="h-3 w-3" />
        <span>Completed</span>
      </span>
    );
  }

  if (isFailed) {
    return (
      <span
        className={`inline-flex items-center font-bold uppercase tracking-wider rounded-full border bg-rose-950/60 text-rose-400 border-rose-800/50 shadow-sm ${sizeClasses}`}
      >
        <AlertCircle className="h-3 w-3" />
        <span>Failed</span>
      </span>
    );
  }

  if (isRunning) {
    return (
      <span
        className={`inline-flex items-center font-bold uppercase tracking-wider rounded-full border bg-blue-950/60 text-blue-400 border-blue-800/50 shadow-sm ${sizeClasses}`}
      >
        <Loader2 className="h-3 w-3 animate-spin" />
        <span>Running</span>
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center font-bold uppercase tracking-wider rounded-full border bg-slate-800 text-slate-300 border-slate-700 shadow-sm ${sizeClasses}`}
    >
      <PlayCircle className="h-3 w-3 text-slate-400" />
      <span>{status || "UNKNOWN"}</span>
    </span>
  );
}
