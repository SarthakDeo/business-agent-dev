"use client";

import { ShieldCheck, Database, Layers } from "lucide-react";

export function Header() {
  return (
    <header className="h-16 bg-slate-900/60 backdrop-blur border-b border-slate-800 px-8 flex items-center justify-between sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-slate-300">Operations Console</h1>
        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
          Phase 11 Foundation
        </span>
      </div>

      <div className="flex items-center gap-4 text-xs">
        {/* PostgreSQL Indicator */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800/80 border border-slate-700 text-slate-300">
          <Database className="h-3.5 w-3.5 text-blue-400" />
          <span>PostgreSQL :5432</span>
        </div>

        {/* Tenant context pill */}
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-indigo-950/60 border border-indigo-700/40 text-indigo-300">
          <ShieldCheck className="h-3.5 w-3.5 text-indigo-400" />
          <span className="font-mono font-medium">org_demo_001</span>
          <span className="text-indigo-500">|</span>
          <span className="font-mono text-indigo-200">user_demo_001</span>
        </div>

        {/* Mode pill */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-950/60 border border-emerald-700/40 text-emerald-300">
          <Layers className="h-3.5 w-3.5 text-emerald-400" />
          <span>ASK / DO / AUTOMATE</span>
        </div>
      </div>
    </header>
  );
}
