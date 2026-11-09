"use client";

import {
  ShieldCheck,
  MessageSquare,
  FileText,
  Layers,
  PlayCircle,
  AlertCircle,
  User,
  Clock,
  Hash,
} from "lucide-react";
import { AuditEvent } from "@/lib/types";
import { formatRelativeTime, getSafeEventSummary } from "@/lib/utils";

interface ActivityEventProps {
  event: AuditEvent;
}

export function ActivityEventItem({ event }: ActivityEventProps) {
  const normType = (event.event_type || "").toUpperCase();
  const summary = getSafeEventSummary(event.event_type, event.mode, event.status, event.metadata);

  const getEventIcon = () => {
    switch (normType) {
      case "AGENT_REQUEST":
        return <MessageSquare className="h-4 w-4 text-indigo-400" />;
      case "PLAN_CREATED":
        return <FileText className="h-4 w-4 text-blue-400" />;
      case "AUTOMATION_CREATED":
      case "AUTOMATION_MODIFIED":
        return <Layers className="h-4 w-4 text-purple-400" />;
      case "EXECUTION_STARTED":
      case "EXECUTION_COMPLETED":
        return <PlayCircle className="h-4 w-4 text-emerald-400" />;
      case "EXECUTION_FAILED":
        return <AlertCircle className="h-4 w-4 text-rose-400" />;
      default:
        return <ShieldCheck className="h-4 w-4 text-slate-400" />;
    }
  };

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
    <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4 hover:border-slate-700/80 transition-colors shadow-sm space-y-3">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-xl bg-slate-800/80 border border-slate-700/50 flex items-center justify-center shrink-0">
            {getEventIcon()}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-white">{event.event_type}</span>
              {event.mode && (
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${getModeBadgeClass(
                    event.mode
                  )}`}
                >
                  {event.mode.toUpperCase()}
                </span>
              )}
              {event.status && (
                <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 uppercase">
                  {event.status}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Timestamp */}
        <span
          className="text-xs text-slate-400 flex items-center gap-1 shrink-0"
          title={new Date(event.created_at).toLocaleString()}
        >
          <Clock className="h-3 w-3 text-slate-500" />
          {formatRelativeTime(event.created_at)}
        </span>
      </div>

      {/* Safe Summary */}
      <p className="text-xs text-slate-300 pl-10 leading-relaxed font-normal">
        {summary}
      </p>

      {/* Safe Metadata & Provenance Row */}
      <div className="pl-10 flex flex-wrap items-center gap-4 pt-1 text-[11px] text-slate-400 border-t border-slate-800/50">
        {event.user_id && (
          <span className="inline-flex items-center gap-1 text-slate-400">
            <User className="h-3 w-3 text-slate-500" />
            <span className="font-mono text-slate-300">{event.user_id}</span>
          </span>
        )}

        {event.run_id && (
          <span className="inline-flex items-center gap-1 text-slate-400 font-mono">
            <Hash className="h-3 w-3 text-slate-500" />
            Run: <span className="text-slate-300">{event.run_id.slice(0, 12)}</span>
          </span>
        )}

        {event.request_id && event.request_id !== event.run_id && (
          <span className="inline-flex items-center gap-1 text-slate-400 font-mono">
            Req: <span className="text-slate-300">{event.request_id.slice(0, 8)}</span>
          </span>
        )}
      </div>
    </div>
  );
}
