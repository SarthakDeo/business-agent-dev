import React from "react";
import Link from "next/link";
import { Activity, ShieldCheck, ArrowRight, RefreshCw, AlertCircle } from "lucide-react";
import { useRecentActivity } from "@/lib/hooks";
import { formatRelativeTime } from "@/lib/utils";
import { clsx } from "clsx";

export function RecentActivitySection() {
  const { data: events, isLoading, isError, refetch, isFetching } = useRecentActivity(5);

  const formatEventType = (type: string) => {
    switch (type) {
      case "AGENT_REQUEST":
        return "Agent Instruction Received";
      case "PLAN_CREATED":
        return "Workflow Plan Synthesized";
      case "TOOL_EXECUTION_COMPLETED":
        return "Tool Execution Completed";
      case "AUTOMATION_CREATED":
        return "Automation Deployed";
      case "AUTOMATION_MODIFIED":
        return "Automation Modified";
      default:
        return type.replace(/_/g, " ").toLowerCase();
    }
  };

  return (
    <div className="rounded-xl bg-slate-900/80 border border-slate-800 p-6 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-indigo-400" />
            <h3 className="font-bold text-white text-sm">Recent Activity</h3>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => refetch()}
              disabled={isFetching}
              title="Refresh activity"
              className="p-1 text-slate-400 hover:text-slate-200 transition-colors"
            >
              <RefreshCw className={clsx("h-3.5 w-3.5", isFetching && "animate-spin")} />
            </button>
            <Link
              href="/activity"
              className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-medium"
            >
              View all
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        </div>

        <div className="mt-4 divide-y divide-slate-800/60">
          {isLoading ? (
            <div className="space-y-4 py-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex gap-3 items-start animate-pulse">
                  <div className="h-6 w-6 rounded bg-slate-800 mt-1" />
                  <div className="space-y-2 flex-1">
                    <div className="h-4 w-3/4 bg-slate-800 rounded" />
                    <div className="h-3 w-1/2 bg-slate-800/60 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : isError ? (
            <div className="py-8 text-center space-y-2">
              <AlertCircle className="h-6 w-6 text-amber-400 mx-auto" />
              <p className="text-xs text-slate-400">Unable to load recent activity.</p>
              <button
                onClick={() => refetch()}
                className="text-xs text-indigo-400 hover:underline"
              >
                Retry
              </button>
            </div>
          ) : !events || events.length === 0 ? (
            <div className="py-8 text-center space-y-2">
              <p className="text-xs text-slate-400 font-medium">No activity recorded yet.</p>
              <p className="text-[11px] text-slate-500">Your Agent activity will appear here as you run tasks.</p>
            </div>
          ) : (
            events.map((e) => (
              <div key={e.id} className="py-3 flex items-start gap-3 first:pt-0 last:pb-0">
                <div className="p-1.5 rounded bg-indigo-950/60 border border-indigo-800/40 text-indigo-400 shrink-0 mt-0.5">
                  <ShieldCheck className="h-3.5 w-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-white capitalize truncate">
                      {formatEventType(e.event_type)}
                    </span>
                    <span className="text-[11px] text-slate-500 whitespace-nowrap">
                      {formatRelativeTime(e.created_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    {e.mode && (
                      <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 border border-slate-700 uppercase">
                        {e.mode}
                      </span>
                    )}
                    {e.run_id && (
                      <span className="text-[10px] text-slate-500 font-mono truncate">
                        Run: {e.run_id.slice(0, 8)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
