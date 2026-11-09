"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Layers, ArrowDown, ShieldCheck, Mail, MessageSquare, Database } from "lucide-react";
import { AutomationStep as AutomationStepType } from "@/lib/types";
import { sanitizeParameters } from "@/lib/utils";

interface AutomationStepProps {
  step: AutomationStepType;
  index: number;
  isLast: boolean;
}

export function AutomationStepCard({ step, index, isLast }: AutomationStepProps) {
  const [paramsExpanded, setParamsExpanded] = useState(true);

  const getToolIcon = () => {
    const tool = (step.tool || "").toLowerCase();
    if (tool.startsWith("gmail")) return Mail;
    if (tool.startsWith("slack")) return MessageSquare;
    if (tool.startsWith("crm")) return Database;
    return Layers;
  };

  const Icon = getToolIcon();
  const sanitizedParams = sanitizeParameters(step.parameters);
  const paramCount = Object.keys(sanitizedParams).length;

  return (
    <div className="relative flex flex-col items-center">
      <div className="w-full rounded-xl bg-slate-900 border border-slate-800 p-4 shadow-sm hover:border-slate-700 transition-colors">
        <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 font-mono text-xs font-bold shrink-0">
              {index + 1}
            </div>

            <div>
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4 text-indigo-400" />
                <h4 className="text-sm font-bold text-white tracking-tight">
                  {step.tool}
                </h4>
              </div>
              <span className="text-[11px] font-mono text-slate-400 block">
                id: {step.id}
              </span>
            </div>
          </div>

          {paramCount > 0 && (
            <button
              type="button"
              onClick={() => setParamsExpanded(!paramsExpanded)}
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors px-2 py-1 rounded bg-slate-800/60 hover:bg-slate-800"
            >
              <span>{paramCount} {paramCount === 1 ? "param" : "params"}</span>
              {paramsExpanded ? (
                <ChevronDown className="h-3.5 w-3.5" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5" />
              )}
            </button>
          )}
        </div>

        {paramsExpanded && paramCount > 0 && (
          <div className="mt-3 space-y-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
              {Object.entries(sanitizedParams).map(([k, v]) => {
                const isReference =
                  typeof v === "string" && v.startsWith("{{") && v.endsWith("}}");
                return (
                  <div
                    key={k}
                    className="p-2 rounded-lg bg-slate-950/80 border border-slate-800/80"
                  >
                    <span className="text-slate-500 text-[11px] block">{k}:</span>
                    <span
                      className={
                        isReference
                          ? "text-emerald-400 font-semibold break-all"
                          : "text-slate-200 break-all"
                      }
                    >
                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </span>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center gap-1.5 text-[10px] text-slate-500 pt-1">
              <ShieldCheck className="h-3 w-3 text-emerald-500/70" />
              <span>References resolved dynamically by Workflow Compiler. Secrets redacted.</span>
            </div>
          </div>
        )}
      </div>

      {/* Downward stem connecting to next step */}
      {!isLast && (
        <div className="flex flex-col items-center my-1.5 text-slate-600">
          <div className="w-0.5 h-6 bg-slate-700" />
          <ArrowDown className="h-4 w-4 -mt-1 text-slate-500" />
        </div>
      )}
    </div>
  );
}
