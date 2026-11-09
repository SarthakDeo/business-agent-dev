import React from "react";
import Link from "next/link";
import { PlayCircle, CheckCircle2, AlertCircle, ArrowRight, RefreshCw } from "lucide-react";
import { useRecentExecutions } from "@/lib/hooks";
import { formatRelativeTime } from "@/lib/utils";
import { clsx } from "clsx";

export function RecentExecutionsSection() {
  const { data: executions, isLoading, isError, refetch, isFetching } = useRecentExecutions(5);

  return (
    <div className="rounded-xl bg-slate-900/80 border border-slate-800 p-6">
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <PlayCircle className="h-4 w-4 text-blue-400" />
          <div>
            <h3 className="font-bold text-white text-sm">Recent Executions</h3>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Live operational tool runs and automated n8n pipeline dispatches.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            title="Refresh executions"
            className="p-1 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <RefreshCw className={clsx("h-3.5 w-3.5", isFetching && "animate-spin")} />
          </button>
          <Link
            href="/executions"
            className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-medium"
          >
            View all
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="space-y-3 py-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex items-center justify-between py-2.5 animate-pulse">
                <div className="flex items-center gap-3">
                  <div className="h-4 w-12 bg-slate-800 rounded" />
                  <div className="h-4 w-28 bg-slate-800 rounded" />
                </div>
                <div className="h-5 w-20 bg-slate-800 rounded-full" />
                <div className="h-4 w-16 bg-slate-800 rounded" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <div className="py-8 text-center space-y-2">
            <AlertCircle className="h-6 w-6 text-amber-400 mx-auto" />
            <p className="text-xs text-slate-400">Unable to load recent executions.</p>
            <button
              onClick={() => refetch()}
              className="text-xs text-indigo-400 hover:underline"
            >
              Retry
            </button>
          </div>
        ) : !executions || executions.length === 0 ? (
          <div className="py-8 text-center space-y-2">
            <p className="text-xs text-slate-400 font-medium">No executions recorded yet.</p>
            <p className="text-[11px] text-slate-500">
              When the Agent executes operational actions or triggers workflows, records appear here.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500 uppercase font-semibold text-[10px] border-b border-slate-800/80">
                <tr>
                  <th className="pb-2.5 font-medium">Mode</th>
                  <th className="pb-2.5 font-medium">Execution ID</th>
                  <th className="pb-2.5 font-medium">Reference</th>
                  <th className="pb-2.5 font-medium">Status</th>
                  <th className="pb-2.5 font-medium text-right">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                {executions.map((x) => {
                  const isSuccess = x.status === "completed" || x.status === "success";
                  return (
                    <tr key={x.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 font-sans">
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700 uppercase">
                          {x.mode}
                        </span>
                      </td>
                      <td className="py-3 text-white font-medium">
                        {x.id}
                      </td>
                      <td className="py-3 text-slate-400 text-[11px]">
                        {x.automation_id || x.request_id || "direct-run"}
                      </td>
                      <td className="py-3">
                        <span
                          className={clsx(
                            "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border",
                            isSuccess
                              ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/50"
                              : "bg-rose-950/60 text-rose-400 border-rose-800/50"
                          )}
                        >
                          {isSuccess ? <CheckCircle2 className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
                          {x.status}
                        </span>
                      </td>
                      <td className="py-3 text-slate-500 text-right text-[11px]">
                        {formatRelativeTime(x.started_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
