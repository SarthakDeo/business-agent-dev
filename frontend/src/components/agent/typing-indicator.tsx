"use client";

import { Bot } from "lucide-react";

interface TypingIndicatorProps {
  label?: string;
}

export function TypingIndicator({ label = "Voice2Flow is thinking..." }: TypingIndicatorProps) {
  return (
    <div className="flex gap-3 items-start animate-in fade-in duration-200">
      <div className="h-8 w-8 rounded-lg bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shrink-0 mt-0.5">
        <Bot className="h-4 w-4 animate-pulse" />
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 flex items-center gap-3 text-xs text-slate-300 shadow-sm">
        <span className="font-medium text-slate-400">{label}</span>
        <div className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.3s]" />
          <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.15s]" />
          <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-bounce" />
        </div>
      </div>
    </div>
  );
}
