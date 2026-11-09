"use client";

import { PendingConfirmationInfo } from "@/lib/types";
import { ModeBadge } from "./mode-badge";
import { ConfirmationDetails } from "./confirmation-details";
import { AlertCircle, CheckCircle2, XCircle, Loader2, ShieldAlert } from "lucide-react";
import { clsx } from "clsx";

interface ConfirmationCardProps {
  runId: string;
  info: PendingConfirmationInfo;
  onConfirm: (approved: boolean) => void;
  loading?: boolean;
}

export function ConfirmationCard({
  runId,
  info,
  onConfirm,
  loading = false,
}: ConfirmationCardProps) {
  const isHighRisk = info.risk?.toLowerCase() === "high";

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={clsx(
        "rounded-xl border p-4.5 sm:p-5 shadow-xl transition-all",
        isHighRisk
          ? "bg-rose-950/60 border-rose-600/50 shadow-rose-950/30"
          : "bg-amber-950/50 border-amber-500/50 shadow-amber-950/20"
      )}
    >
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-amber-900/40">
        <div className="flex items-center gap-2.5">
          {isHighRisk ? (
            <ShieldAlert className="h-5 w-5 text-rose-400 shrink-0" />
          ) : (
            <AlertCircle className="h-5 w-5 text-amber-400 shrink-0" />
          )}
          <div>
            <h4 className="text-sm font-bold text-white tracking-tight">
              Human Approval Required
            </h4>
            <span className="text-[11px] text-amber-300/80">
              Security Boundary — Voice2Flow requires your explicit approval to proceed
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {info.mode && <ModeBadge mode={info.mode} size="xs" />}
          <span
            className={clsx(
              "text-[10px] font-mono font-bold uppercase px-2.5 py-0.5 rounded-full border",
              isHighRisk
                ? "bg-rose-900/70 text-rose-300 border-rose-700/60"
                : "bg-amber-900/60 text-amber-300 border-amber-700/50"
            )}
          >
            Risk: {info.risk || "medium"}
          </span>
        </div>
      </div>

      {/* Summary Description */}
      <div className="mt-3">
        <div className="text-xs font-semibold uppercase tracking-wider text-amber-300/90 mb-1">
          Action Proposal:
        </div>
        <div className="text-xs sm:text-sm text-slate-100 bg-slate-950/70 p-3.5 rounded-lg border border-amber-900/40 font-mono whitespace-pre-wrap leading-relaxed">
          {info.summary}
        </div>
      </div>

      {/* Steps breakdown (sanitized) */}
      <ConfirmationDetails steps={info.steps} runId={runId} />

      {/* Action Buttons */}
      <div className="mt-4 pt-3 border-t border-amber-900/40 flex flex-col-reverse sm:flex-row items-center justify-between gap-3">
        <div className="text-[11px] text-slate-400 font-mono self-start sm:self-center">
          run: {runId}
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
          <button
            type="button"
            onClick={() => onConfirm(false)}
            disabled={loading}
            className="flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 hover:border-slate-600 transition-colors disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />
            ) : (
              <XCircle className="h-3.5 w-3.5 text-rose-400" />
            )}
            <span>Reject Action</span>
          </button>

          <button
            type="button"
            onClick={() => onConfirm(true)}
            disabled={loading}
            className="flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-5 py-2 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/30 transition-colors disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-white" />
            ) : (
              <CheckCircle2 className="h-3.5 w-3.5 text-white" />
            )}
            <span>Approve & Execute</span>
          </button>
        </div>
      </div>
    </div>
  );
}
