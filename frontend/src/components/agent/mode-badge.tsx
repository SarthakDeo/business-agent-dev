"use client";

import { clsx } from "clsx";
import { Compass, Zap, Workflow, HelpCircle, MessageSquare } from "lucide-react";

interface ModeBadgeProps {
  mode?: string | null;
  showDescription?: boolean;
  size?: "xs" | "sm" | "md";
  className?: string;
}

export function ModeBadge({
  mode,
  showDescription = false,
  size = "xs",
  className,
}: ModeBadgeProps) {
  const normalized = (mode || "ASK").toUpperCase();

  const configs: Record<
    string,
    { label: string; desc: string; icon: typeof Compass; classes: string }
  > = {
    CHAT: {
      label: "CHAT",
      desc: "Conversational assistant",
      icon: MessageSquare,
      classes: "bg-emerald-950/70 text-emerald-400 border-emerald-800/60",
    },
    ASK: {
      label: "ASK",
      desc: "Reading information",
      icon: Compass,
      classes: "bg-blue-950/70 text-blue-400 border-blue-800/60",
    },
    DO: {
      label: "DO",
      desc: "One-time action",
      icon: Zap,
      classes: "bg-amber-950/70 text-amber-400 border-amber-800/60",
    },
    AUTOMATE: {
      label: "AUTOMATE",
      desc: "Persistent workflow",
      icon: Workflow,
      classes: "bg-purple-950/70 text-purple-400 border-purple-800/60",
    },
    AUTOMATE_MODIFY: {
      label: "AUTOMATE (MODIFY)",
      desc: "Workflow modification",
      icon: Workflow,
      classes: "bg-fuchsia-950/70 text-fuchsia-400 border-fuchsia-800/60",
    },
  };

  const config = configs[normalized] || {
    label: normalized,
    desc: "System mode",
    icon: HelpCircle,
    classes: "bg-slate-800 text-slate-300 border-slate-700",
  };

  const Icon = config.icon;

  const sizeClasses = {
    xs: "text-[10px] px-2 py-0.5 gap-1",
    sm: "text-xs px-2.5 py-1 gap-1.5",
    md: "text-sm px-3 py-1.5 gap-2",
  }[size];

  return (
    <div className={clsx("inline-flex items-center", className)}>
      <span
        className={clsx(
          "inline-flex items-center font-bold uppercase tracking-wider rounded-full border shadow-sm",
          sizeClasses,
          config.classes
        )}
      >
        <Icon className={size === "xs" ? "h-3 w-3" : "h-3.5 w-3.5"} />
        <span>{config.label}</span>
      </span>
      {showDescription && (
        <span className="ml-2 text-xs text-slate-400 hidden sm:inline">
          {config.desc}
        </span>
      )}
    </div>
  );
}
