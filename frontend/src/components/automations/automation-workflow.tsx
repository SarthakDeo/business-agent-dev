"use client";

import { CanonicalWorkflow } from "@/lib/types";
import { AutomationTriggerCard } from "./automation-trigger";
import { AutomationStepCard } from "./automation-step";
import { Workflow, Layers } from "lucide-react";

interface AutomationWorkflowTimelineProps {
  workflow?: CanonicalWorkflow | null;
}

export function AutomationWorkflowTimeline({
  workflow,
}: AutomationWorkflowTimelineProps) {
  const steps = workflow?.steps || [];
  const trigger = workflow?.trigger || { type: "webhook" };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Workflow className="h-4 w-4 text-indigo-400" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Canonical Workflow DAG
          </h3>
        </div>
        <span className="text-xs text-slate-400 font-mono">
          {steps.length} {steps.length === 1 ? "step" : "steps"}
        </span>
      </div>

      <div className="max-w-2xl mx-auto py-2">
        {/* Trigger Node */}
        <AutomationTriggerCard trigger={trigger} />

        {/* Sequential Step Nodes */}
        {steps.map((step, idx) => (
          <AutomationStepCard
            key={step.id || idx}
            step={step}
            index={idx}
            isLast={idx === steps.length - 1}
          />
        ))}

        {steps.length === 0 && (
          <div className="p-6 text-center text-xs text-slate-500 rounded-xl bg-slate-900 border border-slate-800">
            No action steps configured in this workflow.
          </div>
        )}
      </div>

      <div className="text-center pt-2">
        <div className="inline-flex items-center gap-1.5 text-[11px] text-slate-500 font-mono bg-slate-900/60 px-3 py-1 rounded-full border border-slate-800">
          <Layers className="h-3 w-3 text-indigo-400" />
          <span>Compiled by Voice2Flow Workflow Compiler into n8n execution graph</span>
        </div>
      </div>
    </div>
  );
}
