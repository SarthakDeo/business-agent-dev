"use client";

import { Compass, Zap, Workflow, Search, Sparkles } from "lucide-react";

interface StarterPrompt {
  id: string;
  prompt: string;
  mode: "ASK" | "DO" | "AUTOMATE";
  description: string;
  icon: typeof Search;
}

const STARTER_PROMPTS: StarterPrompt[] = [
  {
    id: "find-john",
    prompt: "Find customer John",
    mode: "ASK",
    description: "Look up customer records and contact history in CRM",
    icon: Search,
  },
  {
    id: "send-slack",
    prompt: "Send a Slack message to the support team",
    mode: "DO",
    description: "Post operational updates to team channels with human approval",
    icon: Zap,
  },
  {
    id: "automate-complaints",
    prompt: "Create an automation for new website complaints",
    mode: "AUTOMATE",
    description: "Compile and deploy an autonomous n8n workflow for incoming issues",
    icon: Workflow,
  },
  {
    id: "recent-orders",
    prompt: "Find my recent orders",
    mode: "ASK",
    description: "Query and summarize delayed or pending fulfillment orders",
    icon: Compass,
  },
];

interface StarterPromptsProps {
  onSelectPrompt: (prompt: string) => void;
  disabled?: boolean;
}

export function StarterPrompts({ onSelectPrompt, disabled = false }: StarterPromptsProps) {
  return (
    <div className="max-w-3xl mx-auto my-auto py-8 px-4 text-center">
      <div className="inline-flex items-center justify-center h-14 w-14 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 mb-4 shadow-lg shadow-indigo-600/10">
        <Sparkles className="h-7 w-7" />
      </div>

      <h3 className="text-xl font-bold text-white tracking-tight mb-2">
        What can I help you accomplish today?
      </h3>
      <p className="text-sm text-slate-400 max-w-lg mx-auto mb-8">
        Voice2Flow orchestrates CRM tools, messaging, and autonomous n8n workflows with human-in-the-loop safety.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
        {STARTER_PROMPTS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => onSelectPrompt(item.prompt)}
              disabled={disabled}
              className="group p-4 rounded-xl bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800 hover:border-indigo-500/50 transition-all text-left shadow-sm disabled:opacity-50 disabled:pointer-events-none"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 text-indigo-400">
                  <Icon className="h-4 w-4 text-indigo-400 group-hover:scale-110 transition-transform" />
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    {item.mode}
                  </span>
                </div>
              </div>
              <div className="font-semibold text-sm text-slate-100 group-hover:text-indigo-300 transition-colors mb-1">
                "{item.prompt}"
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">
                {item.description}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
