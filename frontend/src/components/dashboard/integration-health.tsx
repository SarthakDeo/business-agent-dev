import React from "react";
import Link from "next/link";
import { Plug, Database, Mail, MessageSquare, ArrowRight, RefreshCw, AlertCircle, CheckCircle2, Circle } from "lucide-react";
import { useIntegrationHealth } from "@/lib/hooks";
import { clsx } from "clsx";

export function IntegrationHealthSection() {
  const { data: integrations, isLoading, isError, refetch, isFetching } = useIntegrationHealth();

  const getIcon = (id: string) => {
    switch (id) {
      case "crm":
        return <Database className="h-4 w-4 text-blue-400" />;
      case "gmail":
        return <Mail className="h-4 w-4 text-rose-400" />;
      case "slack":
        return <MessageSquare className="h-4 w-4 text-emerald-400" />;
      default:
        return <Plug className="h-4 w-4 text-indigo-400" />;
    }
  };

  return (
    <div className="rounded-xl bg-slate-900/80 border border-slate-800 p-6 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Plug className="h-4 w-4 text-emerald-400" />
            <h3 className="font-bold text-white text-sm">Integration Health</h3>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => refetch()}
              disabled={isFetching}
              title="Refresh integration status"
              className="p-1 text-slate-400 hover:text-slate-200 transition-colors"
            >
              <RefreshCw className={clsx("h-3.5 w-3.5", isFetching && "animate-spin")} />
            </button>
            <Link
              href="/integrations"
              className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-medium"
            >
              Manage
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {isLoading ? (
            <div className="space-y-3 py-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-slate-800/40 animate-pulse">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded bg-slate-800" />
                    <div className="space-y-1.5">
                      <div className="h-3.5 w-20 bg-slate-800 rounded" />
                      <div className="h-2.5 w-28 bg-slate-800/60 rounded" />
                    </div>
                  </div>
                  <div className="h-5 w-16 bg-slate-800 rounded-full" />
                </div>
              ))}
            </div>
          ) : isError ? (
            <div className="py-8 text-center space-y-2">
              <AlertCircle className="h-6 w-6 text-amber-400 mx-auto" />
              <p className="text-xs text-slate-400">Unable to load integration health.</p>
              <button
                onClick={() => refetch()}
                className="text-xs text-indigo-400 hover:underline"
              >
                Retry
              </button>
            </div>
          ) : !integrations || integrations.length === 0 ? (
            <div className="py-8 text-center space-y-2">
              <p className="text-xs text-slate-400 font-medium">No integrations configured.</p>
              <Link
                href="/integrations"
                className="text-xs text-indigo-400 hover:underline inline-block mt-1"
              >
                Connect tools
              </Link>
            </div>
          ) : (
            integrations.map((item) => {
              const isConnected = item.status === "connected";
              return (
                <div
                  key={item.integration}
                  className="flex items-center justify-between p-3 rounded-lg bg-slate-800/30 border border-slate-800/80 hover:border-slate-700 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="h-8 w-8 rounded-lg bg-slate-800 flex items-center justify-center shrink-0">
                      {getIcon(item.integration)}
                    </div>
                    <div className="min-w-0">
                      <span className="text-xs font-semibold text-white block truncate">
                        {item.name}
                      </span>
                      <span className="text-[11px] text-slate-400 block truncate font-mono">
                        {item.account_identifier ? item.account_identifier : "Ready to connect"}
                      </span>
                    </div>
                  </div>

                  <span
                    className={clsx(
                      "inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full border shrink-0",
                      isConnected
                        ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/50"
                        : "bg-slate-800 text-slate-400 border-slate-700"
                    )}
                  >
                    {isConnected ? (
                      <>
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                        Connected
                      </>
                    ) : (
                      <>
                        <span className="h-1.5 w-1.5 rounded-full bg-slate-500" />
                        Disconnected
                      </>
                    )}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
