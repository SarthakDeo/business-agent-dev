"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Bot,
  Workflow,
  Plug,
  Activity,
  PlayCircle,
  Cpu,
} from "lucide-react";
import { clsx } from "clsx";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/agent", label: "Agent", icon: Bot },
  { href: "/automations", label: "Automations", icon: Workflow },
  { href: "/integrations", label: "Integrations", icon: Plug },
  { href: "/activity", label: "Activity", icon: Activity },
  { href: "/executions", label: "Executions", icon: PlayCircle },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col shrink-0 min-h-screen">
      {/* Brand Header */}
      <div className="h-16 flex items-center gap-3 px-6 border-b border-slate-800">
        <div className="h-9 w-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-md shadow-indigo-600/30">
          <Cpu className="h-5 w-5" />
        </div>
        <div>
          <span className="font-bold text-lg tracking-tight text-white">Voice2Flow</span>
          <span className="block text-[10px] text-slate-400 font-medium uppercase tracking-wider">Business Agent</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 font-semibold"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
              )}
            >
              <Icon className={clsx("h-4 w-4", isActive ? "text-indigo-400" : "text-slate-400")} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-800 text-xs text-slate-500">
        <div className="flex items-center justify-between mb-1">
          <span>Backend API</span>
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
        </div>
        <p className="truncate text-[11px] text-slate-400">FastAPI :8000</p>
      </div>
    </aside>
  );
}
