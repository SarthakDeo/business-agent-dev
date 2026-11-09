"use client";

import { useState, useRef, useEffect } from "react";
import { Send, CornerDownLeft } from "lucide-react";
import { clsx } from "clsx";

interface ChatInputProps {
  onSend: (message: string) => void;
  loading?: boolean;
  disabled?: boolean;
  disabledReason?: string;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  loading = false,
  disabled = false,
  disabledReason,
  placeholder = "Ask a question, request an action, or describe an automation to build...",
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (disabled || loading || !value.trim()) return;
    onSend(value.trim());
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [value]);

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div
        className={clsx(
          "rounded-2xl bg-slate-900 border transition-all flex flex-col p-2",
          disabled
            ? "border-slate-800 bg-slate-900/60 opacity-80"
            : "border-slate-800 focus-within:border-indigo-500/80 focus-within:ring-1 focus-within:ring-indigo-500/30"
        )}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled || loading}
          rows={1}
          placeholder={disabledReason || placeholder}
          className="w-full bg-transparent px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none resize-none disabled:cursor-not-allowed leading-relaxed"
          style={{ minHeight: "44px", maxHeight: "160px" }}
        />

        <div className="flex items-center justify-between pt-1 px-2 border-t border-slate-800/60 text-xs text-slate-500">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
            <CornerDownLeft className="h-3 w-3" />
            <span className="hidden sm:inline">Press <kbd className="px-1 py-0.5 rounded bg-slate-800 text-slate-400 font-mono text-[10px]">Enter</kbd> to send, <kbd className="px-1 py-0.5 rounded bg-slate-800 text-slate-400 font-mono text-[10px]">Shift+Enter</kbd> for new line</span>
          </div>

          <button
            type="submit"
            disabled={disabled || loading || !value.trim()}
            aria-label="Send message"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs shadow-md shadow-indigo-600/20 disabled:opacity-40 disabled:hover:bg-indigo-600 transition-colors"
          >
            <span>Send</span>
            <Send className="h-3 w-3" />
          </button>
        </div>
      </div>
    </form>
  );
}
