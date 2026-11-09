import React from "react";
import Link from "next/link";
import { Bot, ArrowRight, Sparkles, MessageSquareCode } from "lucide-react";

export function AgentCtaSection() {
  const suggestions = [
    { label: "Check delayed orders", mode: "ASK" },
    { label: "Send Slack logistics announcement", mode: "DO" },
    { label: "Automate daily order follow-up", mode: "AUTOMATE" },
  ];

  return (
    <div className="rounded-xl bg-gradient-to-r from-indigo-950/70 via-slate-900 to-slate-900 border border-indigo-800/40 p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-indigo-400 text-xs font-semibold uppercase tracking-wider">
          <Sparkles className="h-3.5 w-3.5" />
          <span>Interactive Orchestrator</span>
        </div>
        <h3 className="text-xl font-bold text-white tracking-tight">
          What can Voice2Flow do for your business today?
        </h3>
        <p className="text-xs text-slate-400 max-w-xl">
          Ask natural-language questions, execute operational workflows across Gmail, Slack, and CRM, or synthesize autonomous n8n automations.
        </p>

        {/* Suggestion Chips */}
        <div className="flex flex-wrap items-center gap-2 pt-2">
          {suggestions.map((s) => (
            <Link
              key={s.label}
              href="/agent"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800/90 hover:bg-slate-700/90 text-slate-300 text-xs border border-slate-700 hover:border-slate-600 transition-colors"
            >
              <span className="text-[9px] font-bold uppercase text-indigo-400">
                {s.mode}:
              </span>
              <span>{s.label}</span>
            </Link>
          ))}
        </div>
      </div>

      <Link
        href="/agent"
        className="flex items-center gap-2 px-5 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold shadow-lg shadow-indigo-600/30 transition-all shrink-0 hover:scale-[1.02]"
      >
        <Bot className="h-4 w-4" />
        <span>Talk to Voice2Flow</span>
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
