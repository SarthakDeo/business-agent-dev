"use client";

import Link from "next/link";
import { Bot, User, Cpu, ExternalLink, AlertCircle, CheckCircle2, Mic } from "lucide-react";
import { clsx } from "clsx";
import { ChatMessage as ChatMessageType } from "@/lib/types";
import { ModeBadge } from "./mode-badge";
import { StatusBadge } from "./status-badge";
import { formatRelativeTime } from "@/lib/utils";

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isAgent = message.role === "assistant";
  const isSystem = message.role === "system";

  // Check if an automation ID exists in execution results
  const automationData = (message.executionResults?.automation as Record<string, unknown>) || null;
  const automationId = message.automationId || (automationData?.automation_id as string) || (automationData?.id as string);
  const n8nWorkflowId = (automationData?.n8n_workflow_id as string) || null;

  return (
    <div
      className={clsx(
        "flex gap-3 group animate-in fade-in duration-150",
        isAgent ? "justify-start" : isSystem ? "justify-center" : "justify-end"
      )}
    >
      {/* Agent Avatar */}
      {isAgent && (
        <div className="h-8 w-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shrink-0 mt-1 shadow-sm">
          <Bot className="h-4 w-4" />
        </div>
      )}

      {/* Message Bubble Container */}
      <div
        className={clsx(
          "max-w-3xl rounded-2xl p-4 text-sm leading-relaxed shadow-sm transition-all",
          isAgent
            ? "bg-slate-900 border border-slate-800 text-slate-100"
            : isSystem
            ? "bg-slate-900/60 border border-slate-800/80 text-slate-300 text-center text-xs py-2 px-4"
            : "bg-indigo-600 text-white font-medium shadow-indigo-600/20"
        )}
      >
        {/* Header metadata for Assistant message */}
        {isAgent && (
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2 pb-2 border-b border-slate-800/60">
            <div className="flex items-center gap-2">
              <span className="font-bold text-xs text-white">Voice2Flow Agent</span>
              {message.mode && <ModeBadge mode={message.mode} size="xs" />}
              {message.status && <StatusBadge status={message.status} size="xs" />}
            </div>

            <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono">
              {message.runId && (
                <span title={`Run ID: ${message.runId}`}>
                  run:{message.runId.slice(0, 8)}
                </span>
              )}
              <span>{formatRelativeTime(message.timestamp)}</span>
            </div>
          </div>
        )}

        {/* User voice tag */}
        {!isAgent && !isSystem && message.isVoice && (
          <div className="flex items-center gap-1.5 text-[11px] text-indigo-200 font-semibold mb-1 pb-1 border-b border-indigo-400/30">
            <Mic className="h-3 w-3 text-indigo-200" />
            <span>You said (Voice)</span>
          </div>
        )}

        {/* Text Content */}
        <div className="whitespace-pre-wrap break-words">{message.content}</div>

        {/* Automation Created Link (Phase 11D requirement Section 19) */}
        {automationId && (
          <div className="mt-3 p-3 rounded-lg bg-indigo-950/50 border border-indigo-800/50 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
              <div className="text-xs">
                <span className="font-semibold text-slate-200">Autonomous Workflow Deployed</span>
                {n8nWorkflowId && (
                  <span className="text-slate-400 font-mono text-[11px] block">
                    n8n Workflow ID: {n8nWorkflowId}
                  </span>
                )}
              </div>
            </div>

            <Link
              href={`/automations/${automationId}`}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-indigo-600/80 hover:bg-indigo-600 text-white text-xs font-semibold shadow-sm transition-colors"
            >
              <span>View Automation</span>
              <ExternalLink className="h-3 w-3" />
            </Link>
          </div>
        )}

        {/* Error Callout inside message if present */}
        {message.error && (
          <div className="mt-2.5 p-2.5 rounded-lg bg-rose-950/50 border border-rose-900/60 text-xs text-rose-300 flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-bold text-[11px] text-rose-200">
                {message.errorCode || "Agent Error"}
              </div>
              <div className="text-[11px] text-rose-300/90 leading-normal font-sans">
                {message.error}
              </div>
            </div>
          </div>
        )}

        {/* Footer timestamp for user message */}
        {!isAgent && !isSystem && (
          <div className="text-[10px] text-indigo-200/70 text-right mt-1 font-mono">
            {formatRelativeTime(message.timestamp)}
          </div>
        )}
      </div>

      {/* User Avatar */}
      {!isAgent && !isSystem && (
        <div className="h-8 w-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0 mt-1 shadow-sm">
          <User className="h-4 w-4" />
        </div>
      )}
    </div>
  );
}
