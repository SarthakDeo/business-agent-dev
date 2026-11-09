"use client";

import { Mic } from "lucide-react";

interface StarterPrompt {
  id: string;
  prompt: string;
  mode: "ASK" | "DO" | "AUTOMATE";
  description: string;
}

const VOICE_STARTER_PROMPTS: StarterPrompt[] = [
  {
    id: "find-order",
    prompt: "Find my latest customer order.",
    mode: "ASK",
    description: "Query and inspect customer order statuses in CRM",
  },
  {
    id: "send-slack",
    prompt: "Send a Slack message to the support channel.",
    mode: "DO",
    description: "Post operational announcement to #support with confirmation",
  },
  {
    id: "gmail-slack",
    prompt: "Whenever I receive a Gmail, notify my support team in Slack.",
    mode: "AUTOMATE",
    description: "Synthesize an autonomous trigger-and-action workflow in n8n",
  },
  {
    id: "ticket-complaint",
    prompt: "Create a support ticket when a customer complaint arrives.",
    mode: "AUTOMATE",
    description: "Build an event-driven complaint resolution pipeline",
  },
];

interface StarterPromptsProps {
  onSelectPrompt: (prompt: string) => void;
  disabled?: boolean;
}

export function StarterPrompts({ onSelectPrompt, disabled = false }: StarterPromptsProps) {
  return (
    <div className="w-full max-w-3xl mx-auto py-4 px-2">
      <div className="flex items-center gap-2 mb-3">
        <Mic className="h-4 w-4 text-indigo-400" />
        <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
          Try saying to Voice2Flow:
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-left">
        {VOICE_STARTER_PROMPTS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelectPrompt(item.prompt)}
            disabled={disabled}
            className="group p-3.5 rounded-xl bg-slate-900/70 hover:bg-slate-800/90 border border-slate-800/90 hover:border-indigo-500/40 transition-all text-left shadow-sm disabled:opacity-40 disabled:pointer-events-none"
          >
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-1.5 text-indigo-400">
                <span className="text-sm">🎙</span>
                <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
                  {item.mode}
                </span>
              </div>
            </div>
            <div className="font-semibold text-xs text-slate-100 group-hover:text-indigo-300 transition-colors">
              "{item.prompt}"
            </div>
            <div className="text-[11px] text-slate-400 mt-1 line-clamp-1">
              {item.description}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
