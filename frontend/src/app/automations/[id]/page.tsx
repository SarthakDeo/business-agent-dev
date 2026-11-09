"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft, Workflow, Clock, Hash, Bot, Sparkles, Building2, ExternalLink } from "lucide-react";
import { useAutomationDetail } from "@/lib/hooks";
import { AutomationStatusBadge } from "@/components/automations/automation-status";
import { AutomationWorkflowTimeline } from "@/components/automations/automation-workflow";
import { ErrorMessage } from "@/components/agent/error-message";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function AutomationDetailPage({ params }: PageProps) {
  const { id } = use(params);
  const { data: automation, isLoading, error, refetch } = useAutomationDetail(id);

  const is404 =
    error instanceof Error &&
    (error.message.includes("404") || error.message.toLowerCase().includes("not found"));

  if (is404) {
    return (
      <div className="max-w-4xl mx-auto py-12 text-center space-y-4">
        <div className="h-14 w-14 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500 mx-auto">
          <Workflow className="h-7 w-7" />
        </div>
        <h2 className="text-xl font-bold text-white tracking-tight">Automation Not Found</h2>
        <p className="text-xs text-slate-400 max-w-sm mx-auto">
          The requested automation ID <span className="font-mono text-slate-300">"{id}"</span> could not be found or does not belong to your organization.
        </p>
        <div className="pt-2">
          <Link
            href="/automations"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors border border-slate-700"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to Automations</span>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back Button & Top Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/automations"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Automations</span>
        </Link>

        {automation && (
          <Link
            href={`/agent?prompt=Modify automation ${automation.name} to `}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-semibold transition-colors"
          >
            <Bot className="h-3.5 w-3.5" />
            <span>Modify with Voice2Flow</span>
          </Link>
        )}
      </div>

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-6 space-y-6 animate-pulse">
          <div className="h-8 bg-slate-800 rounded w-1/3" />
          <div className="h-4 bg-slate-800/60 rounded w-1/2" />
          <div className="h-64 bg-slate-800/30 rounded-xl" />
        </div>
      )}

      {/* Error Banner */}
      {error && !is404 && (
        <ErrorMessage error={error} onRetry={() => refetch()} />
      )}

      {/* Detail Content */}
      {automation && (
        <>
          {/* Header Card */}
          <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6 shadow-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-3">
                  <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                    {automation.name}
                  </h1>
                  <AutomationStatusBadge status={automation.status} size="sm" />
                </div>
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 font-mono pt-1">
                  <span className="flex items-center gap-1">
                    <Hash className="h-3.5 w-3.5 text-slate-500" />
                    {automation.id}
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Building2 className="h-3.5 w-3.5 text-slate-500" />
                    {automation.organization_id}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2 self-start sm:self-center">
                <div className="text-right text-xs text-slate-400 font-mono">
                  <span className="block text-[10px] uppercase text-slate-500">n8n Workflow ID</span>
                  <span className="text-slate-200">{automation.n8n_workflow_id}</span>
                </div>
              </div>
            </div>

            {/* Timestamps */}
            <div className="pt-3 border-t border-slate-800 flex flex-wrap items-center gap-4 text-xs text-slate-400 font-mono">
              <div className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-slate-500" />
                <span>Created: {new Date(automation.created_at).toLocaleString()}</span>
              </div>
              <span>•</span>
              <div className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-indigo-400" />
                <span>Updated: {new Date(automation.updated_at).toLocaleString()}</span>
              </div>
            </div>
          </div>

          {/* Workflow DAG Visualization */}
          <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-6 shadow-md">
            <AutomationWorkflowTimeline workflow={automation.canonical_workflow} />
          </div>

          {/* About & Metadata Card */}
          <div className="rounded-2xl bg-slate-900/40 border border-slate-800 p-5 space-y-3">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400">
              <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
              <span>About this Automation</span>
            </div>

            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
              This automation is managed under Voice2Flow's canonical workflow model. All modifications, trigger changes, and tool integrations are validated through the Agent Core security boundary and compiled into n8n for durable execution.
            </p>

            <div className="pt-2 flex items-center justify-between text-xs text-slate-500 font-mono border-t border-slate-800/80">
              <span>Security Boundary: Active</span>
              <span>Tenant Isolated: {automation.organization_id}</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
