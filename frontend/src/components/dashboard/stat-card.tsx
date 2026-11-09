import React from "react";
import { LucideIcon, AlertCircle } from "lucide-react";
import { clsx } from "clsx";

interface StatCardProps {
  title: string;
  value: number | undefined;
  description?: string;
  icon: LucideIcon;
  isLoading: boolean;
  isError: boolean;
  iconColor?: string;
}

export function StatCard({
  title,
  value,
  description,
  icon: Icon,
  isLoading,
  isError,
  iconColor = "text-indigo-400",
}: StatCardProps) {
  return (
    <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 flex flex-col justify-between hover:border-slate-700 transition-colors">
      <div className="flex items-center justify-between text-slate-400">
        <span className="text-xs font-semibold uppercase tracking-wider">{title}</span>
        <div className={clsx("p-2 rounded-lg bg-slate-800/80", iconColor)}>
          <Icon className="h-4 w-4" />
        </div>
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="space-y-2">
            <div className="h-8 w-16 bg-slate-800 rounded animate-pulse" />
            <div className="h-3 w-24 bg-slate-800/60 rounded animate-pulse" />
          </div>
        ) : isError ? (
          <div className="flex items-center gap-1.5 text-xs text-amber-400 mt-2">
            <AlertCircle className="h-4 w-4" />
            <span>Unavailable</span>
          </div>
        ) : (
          <>
            <span className="text-3xl font-extrabold text-white tracking-tight">
              {value ?? 0}
            </span>
            {description && (
              <span className="text-xs text-slate-400 block mt-1">
                {description}
              </span>
            )}
          </>
        )}
      </div>
    </div>
  );
}
