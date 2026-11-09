import React from "react";
import Link from "next/link";
import { Bot, Workflow, Plug, Activity, ArrowRight } from "lucide-react";

export function QuickActionsSection() {
  const actions = [
    {
      title: "Talk to Voice2Flow",
      description: "Ask questions, run actions, or build workflows",
      href: "/agent",
      icon: Bot,
      color: "text-indigo-400",
      bg: "bg-indigo-950/50",
    },
    {
      title: "View Automations",
      description: "Inspect canonical workflows & n8n triggers",
      href: "/automations",
      icon: Workflow,
      color: "text-purple-400",
      bg: "bg-purple-950/50",
    },
    {
      title: "Connect Integration",
      description: "Manage CRM, Gmail, and Slack tool access",
      href: "/integrations",
      icon: Plug,
      color: "text-emerald-400",
      bg: "bg-emerald-950/50",
    },
    {
      title: "View Activity",
      description: "Inspect PostgreSQL audited events and logs",
      href: "/activity",
      icon: Activity,
      color: "text-blue-400",
      bg: "bg-blue-950/50",
    },
  ];

  return (
    <div>
      <h4 className="text-xs font-semibold uppercase text-slate-400 tracking-wider mb-3">
        Quick Actions
      </h4>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {actions.map((act) => {
          const Icon = act.icon;
          return (
            <Link
              key={act.title}
              href={act.href}
              className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 transition-all flex items-center justify-between group"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className={`p-2 rounded-lg ${act.bg} ${act.color} shrink-0`}>
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <span className="text-xs font-semibold text-white block group-hover:text-indigo-300 transition-colors truncate">
                    {act.title}
                  </span>
                  <span className="text-[11px] text-slate-500 block truncate">
                    {act.description}
                  </span>
                </div>
              </div>
              <ArrowRight className="h-3.5 w-3.5 text-slate-600 group-hover:text-slate-300 group-hover:translate-x-0.5 transition-all shrink-0 ml-2" />
            </Link>
          );
        })}
      </div>
    </div>
  );
}
