"use client";

import React from "react";
import { Workflow, Plug, PlayCircle, AlertTriangle, Cpu } from "lucide-react";
import { useDashboardStats, useApiHealth } from "@/lib/hooks";
import { StatCard } from "@/components/dashboard/stat-card";
import { AgentCtaSection } from "@/components/dashboard/agent-cta";
import { RecentActivitySection } from "@/components/dashboard/recent-activity";
import { IntegrationHealthSection } from "@/components/dashboard/integration-health";
import { RecentExecutionsSection } from "@/components/dashboard/recent-executions";
import { QuickActionsSection } from "@/components/dashboard/quick-actions";

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading, isError: statsError } = useDashboardStats();
  const { data: health } = useApiHealth();

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* 1. Header / Welcome Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2">
        <div>
          <h2 className="text-2xl font-extrabold text-white tracking-tight">
            Business Operations Overview
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Real-time telemetry, autonomous n8n workflows, and audited AI Agent executions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
            <span
              className={`h-2 w-2 rounded-full ${
                health?.status === "ok" ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
              }`}
            />
            <span className="font-medium text-slate-300">System Gateway:</span>
            <span className="font-mono text-emerald-400">
              {health?.status === "ok" ? "Connected (:8000)" : "Connecting..."}
            </span>
          </div>
        </div>
      </div>

      {/* 2. Key Metrics Statistics Cards (5 Metrics) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Automations"
          value={stats?.automations}
          description="Total defined workflows"
          icon={Workflow}
          isLoading={statsLoading}
          isError={statsError}
          iconColor="text-indigo-400"
        />
        <StatCard
          title="Active Automations"
          value={stats?.active_automations}
          description="Running in n8n engine"
          icon={Cpu}
          isLoading={statsLoading}
          isError={statsError}
          iconColor="text-purple-400"
        />
        <StatCard
          title="Integrations"
          value={stats?.integrations}
          description="Connected services"
          icon={Plug}
          isLoading={statsLoading}
          isError={statsError}
          iconColor="text-emerald-400"
        />
        <StatCard
          title="Executions"
          value={stats?.recent_executions}
          description="Recorded runs"
          icon={PlayCircle}
          isLoading={statsLoading}
          isError={statsError}
          iconColor="text-blue-400"
        />
        <StatCard
          title="Recent Errors"
          value={stats?.recent_errors}
          description="Blocked or failed tasks"
          icon={AlertTriangle}
          isLoading={statsLoading}
          isError={statsError}
          iconColor="text-amber-400"
        />
      </div>

      {/* 3. Interactive Agent CTA Banner */}
      <AgentCtaSection />

      {/* 4. Two-Column Section: Recent Activity & Integration Health */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RecentActivitySection />
        <IntegrationHealthSection />
      </div>

      {/* 5. Full-Width Section: Recent Executions */}
      <RecentExecutionsSection />

      {/* 6. Quick Navigation Actions Bar */}
      <QuickActionsSection />
    </div>
  );
}
