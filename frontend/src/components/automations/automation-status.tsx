"use client";

import { clsx } from "clsx";
import { CheckCircle2, PauseCircle, Clock, Sparkles } from "lucide-react";

interface AutomationStatusBadgeProps {
  status?: string | null;
  size?: "xs" | "sm";
  className?: string;
}

export function AutomationStatusBadge({
  status,
  size = "xs",
  className,
}: AutomationStatusBadgeProps) {
  const norm = (status || "created").toLowerCase();

  const configs: Record<
    string,
    { label: string; icon: typeof CheckCircle2; classes: string }
  > = {
    active: {
      label: "Active",
      icon: CheckCircle2,
      classes: "bg-emerald-950/60 text-emerald-400 border-emerald-800/50",
    },
    created: {
      label: "Active",
      icon: CheckCircle2,
      classes: "bg-emerald-950/60 text-emerald-400 border-emerald-800/50",
    },
    updated: {
      label: "Updated",
      icon: Sparkles,
      classes: "bg-indigo-950/60 text-indigo-300 border-indigo-800/50",
    },
    inactive: {
      label: "Inactive",
      icon: PauseCircle,
      classes: "bg-slate-800/80 text-slate-400 border-slate-700",
    },
    paused: {
      label: "Paused",
      icon: PauseCircle,
      classes: "bg-amber-950/60 text-amber-400 border-amber-800/50",
    },
  };

  const config = configs[norm] || {
    label: norm.charAt(0).toUpperCase() + norm.slice(1),
    icon: Clock,
    classes: "bg-slate-800 text-slate-300 border-slate-700",
  };

  const Icon = config.icon;

  const sizeClasses = {
    xs: "text-[10px] px-2 py-0.5 gap-1",
    sm: "text-xs px-2.5 py-1 gap-1.5",
  }[size];

  return (
    <span
      className={clsx(
        "inline-flex items-center font-semibold rounded-full border shadow-sm",
        sizeClasses,
        config.classes,
        className
      )}
    >
      <Icon className={size === "xs" ? "h-3 w-3" : "h-3.5 w-3.5"} />
      <span>{config.label}</span>
    </span>
  );
}
