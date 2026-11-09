"use client";

import { Webhook, Clock, Zap, ArrowDown } from "lucide-react";
import { AutomationTrigger as AutomationTriggerType } from "@/lib/types";
import { sanitizeParameters } from "@/lib/utils";

interface AutomationTriggerProps {
  trigger?: AutomationTriggerType | null;
}

export function AutomationTriggerCard({ trigger }: AutomationTriggerProps) {
  const triggerType = (trigger?.type || "webhook").toLowerCase();

  const getTriggerIcon = () => {
    switch (triggerType) {
      case "cron":
      case "schedule":
      case "interval":
        return Clock;
      case "event":
        return Zap;
      case "webhook":
      default:
        return Webhook;
    }
  };

  const Icon = getTriggerIcon();
  const sanitizedParams = sanitizeParameters(trigger?.parameters);

  return (
    <div className="relative flex flex-col items-center">
      <div className="w-full rounded-xl bg-slate-900 border border-indigo-500/40 p-4 shadow-md shadow-indigo-950/20 hover:border-indigo-500/60 transition-colors">
        <div className="flex items-center justify-between pb-2 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
              <Icon className="h-4 w-4" />
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold tracking-wider text-indigo-400 block">
                Workflow Trigger
              </span>
              <h4 className="text-sm font-bold text-white capitalize">
                {triggerType} Trigger
              </h4>
            </div>
          </div>

          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-800/40 uppercase">
            Type: {triggerType}
          </span>
        </div>

        {Object.keys(sanitizedParams).length > 0 ? (
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            {Object.entries(sanitizedParams).map(([k, v]) => (
              <div
                key={k}
                className="bg-slate-950/80 p-2 rounded-lg border border-slate-800/80 font-mono"
              >
                <span className="text-slate-400 text-[11px] block">{k}:</span>
                <span className="text-indigo-300 font-semibold break-all text-xs">
                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-2 text-xs text-slate-500 italic">
            Default event listener configuration
          </div>
        )}
      </div>

      {/* Downward connection stem */}
      <div className="flex flex-col items-center my-1.5 text-indigo-400">
        <div className="w-0.5 h-6 bg-indigo-500/50" />
        <ArrowDown className="h-4 w-4 -mt-1 text-indigo-400" />
      </div>
    </div>
  );
}
