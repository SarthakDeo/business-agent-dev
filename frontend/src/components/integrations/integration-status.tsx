"use client";

import { clsx } from "clsx";
import { CheckCircle2, XCircle, AlertCircle } from "lucide-react";

interface IntegrationStatusBadgeProps {
  status?: string | null;
  size?: "xs" | "sm";
  className?: string;
}

export function IntegrationStatusBadge({
  status,
  size = "xs",
  className,
}: IntegrationStatusBadgeProps) {
  const isConnected = (status || "").toLowerCase() === "connected";

  const sizeClasses = {
    xs: "text-[10px] px-2 py-0.5 gap-1",
    sm: "text-xs px-2.5 py-1 gap-1.5",
  }[size];

  return (
    <span
      className={clsx(
        "inline-flex items-center font-bold uppercase tracking-wider rounded-full border shadow-sm",
        sizeClasses,
        isConnected
          ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/50"
          : "bg-slate-800 text-slate-400 border-slate-700",
        className
      )}
    >
      {isConnected ? (
        <>
          <CheckCircle2 className={size === "xs" ? "h-3 w-3" : "h-3.5 w-3.5"} />
          <span>Connected</span>
        </>
      ) : (
        <>
          <XCircle className={size === "xs" ? "h-3 w-3 text-slate-500" : "h-3.5 w-3.5 text-slate-500"} />
          <span>Disconnected</span>
        </>
      )}
    </span>
  );
}
