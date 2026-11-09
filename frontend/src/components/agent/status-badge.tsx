"use client";

import { clsx } from "clsx";
import { CheckCircle2, Clock, AlertTriangle, ShieldAlert, Loader2 } from "lucide-react";

interface StatusBadgeProps {
  status?: string | null;
  size?: "xs" | "sm";
  className?: string;
}

export function StatusBadge({ status, size = "xs", className }: StatusBadgeProps) {
  const norm = (status || "completed").toLowerCase();

  const configs: Record<
    string,
    { label: string; icon: typeof CheckCircle2; classes: string; animate?: boolean }
  > = {
    completed: {
      label: "Completed",
      icon: CheckCircle2,
      classes: "bg-emerald-950/60 text-emerald-400 border-emerald-800/50",
    },
    awaiting_confirmation: {
      label: "Awaiting Approval",
      icon: Clock,
      classes: "bg-amber-950/70 text-amber-300 border-amber-700/60",
      animate: true,
    },
    error: {
      label: "Failed",
      icon: AlertTriangle,
      classes: "bg-rose-950/60 text-rose-400 border-rose-800/50",
    },
    blocked: {
      label: "Security Blocked",
      icon: ShieldAlert,
      classes: "bg-red-950/70 text-red-300 border-red-800/60",
    },
    running: {
      label: "Processing",
      icon: Loader2,
      classes: "bg-indigo-950/60 text-indigo-400 border-indigo-800/50",
      animate: true,
    },
  };

  const config = configs[norm] || {
    label: norm,
    icon: CheckCircle2,
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
        "inline-flex items-center font-medium rounded-full border",
        sizeClasses,
        config.classes,
        className
      )}
    >
      <Icon
        className={clsx(
          size === "xs" ? "h-3 w-3" : "h-3.5 w-3.5",
          config.animate && norm === "running" && "animate-spin"
        )}
      />
      <span>{config.label}</span>
    </span>
  );
}
