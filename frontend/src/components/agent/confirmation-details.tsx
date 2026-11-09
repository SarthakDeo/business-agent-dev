"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Layers, Tag, ShieldCheck } from "lucide-react";
import { sanitizeParameters } from "@/lib/utils";

interface ConfirmationDetailsProps {
  steps?: Array<Record<string, unknown>>;
  runId?: string;
}

export function ConfirmationDetails({ steps = [], runId }: ConfirmationDetailsProps) {
  const [expanded, setExpanded] = useState(false);

  if (!steps || steps.length === 0) return null;

  return (
    <div className="mt-3 border-t border-amber-900/40 pt-3">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs font-semibold text-amber-300 hover:text-amber-200 transition-colors"
      >
        {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        <span>Inspect Execution Plan ({steps.length} {steps.length === 1 ? "step" : "steps"})</span>
        {runId && (
          <span className="font-mono text-[10px] text-amber-400/70 ml-auto">
            run: {runId.slice(0, 8)}...
          </span>
        )}
      </button>

      {expanded && (
        <div className="mt-2.5 space-y-2 text-xs">
          {steps.map((step, idx) => {
            const tool = (step.tool as string) || (step.id as string) || `Step ${idx + 1}`;
            const rawParams = (step.parameters as Record<string, unknown>) || {};
            const sanitizedParams = sanitizeParameters(rawParams);

            return (
              <div
                key={idx}
                className="p-2.5 rounded-lg bg-slate-950/70 border border-amber-900/40 text-slate-300"
              >
                <div className="flex items-center justify-between font-mono text-[11px] mb-1.5 text-amber-300">
                  <div className="flex items-center gap-1.5">
                    <Layers className="h-3 w-3 text-amber-400" />
                    <span className="font-semibold">{tool}</span>
                  </div>
                  {Boolean(step.id) && (
                    <span className="text-[10px] text-slate-500">ID: {String(step.id)}</span>
                  )}
                </div>

                {Object.keys(sanitizedParams).length > 0 ? (
                  <div className="grid grid-cols-1 gap-1 text-[11px] font-mono mt-1 text-slate-400">
                    {Object.entries(sanitizedParams).map(([paramKey, paramVal]) => (
                      <div key={paramKey} className="flex items-start gap-2 bg-slate-900/80 p-1.5 rounded">
                        <span className="text-amber-400/80 shrink-0">{paramKey}:</span>
                        <span className="text-slate-200 break-all">
                          {typeof paramVal === "object"
                            ? JSON.stringify(paramVal)
                            : String(paramVal)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-[10px] text-slate-500 italic">No parameters</div>
                )}
              </div>
            );
          })}

          <div className="flex items-center gap-1 text-[10px] text-emerald-400/90 pt-1">
            <ShieldCheck className="h-3 w-3" />
            <span>Sensitive tokens and keys are sanitized by security policy.</span>
          </div>
        </div>
      )}
    </div>
  );
}
