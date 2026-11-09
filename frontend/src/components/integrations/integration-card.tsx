"use client";

import { Mail, MessageSquare, Database, Plug, Clock, User, ShieldCheck } from "lucide-react";
import { IntegrationStatus } from "@/lib/types";
import { IntegrationStatusBadge } from "./integration-status";
import { getIntegrationMetadata, formatRelativeTime } from "@/lib/utils";

interface IntegrationCardProps {
  integration: IntegrationStatus;
  onConnectClick: (integration: IntegrationStatus) => void;
  onDisconnectClick: (integration: IntegrationStatus) => void;
  disabled?: boolean;
}

export function IntegrationCard({
  integration,
  onConnectClick,
  onDisconnectClick,
  disabled = false,
}: IntegrationCardProps) {
  const isConnected = (integration.status || "").toLowerCase() === "connected";
  const meta = getIntegrationMetadata(integration.integration);

  const getServiceIcon = () => {
    switch (integration.integration.toLowerCase()) {
      case "gmail":
        return <Mail className="h-5 w-5 text-rose-400" />;
      case "slack":
        return <MessageSquare className="h-5 w-5 text-emerald-400" />;
      case "crm":
        return <Database className="h-5 w-5 text-blue-400" />;
      default:
        return <Plug className="h-5 w-5 text-indigo-400" />;
    }
  };

  return (
    <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5 flex flex-col justify-between hover:border-slate-700/80 transition-all duration-200 shadow-sm space-y-5">
      <div className="space-y-4">
        {/* Header: Icon, Name & Status */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-11 w-11 rounded-xl bg-slate-800/80 border border-slate-700/50 flex items-center justify-center shrink-0">
              {getServiceIcon()}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-white text-sm">{integration.name}</h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700 font-medium">
                  {meta.category}
                </span>
              </div>
              <span className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5 font-mono">
                <ShieldCheck className="h-3 w-3 text-indigo-400" />
                {meta.authTypeLabel}
              </span>
            </div>
          </div>

          <IntegrationStatusBadge status={integration.status} />
        </div>

        {/* Description */}
        <p className="text-xs text-slate-400 leading-relaxed min-h-[32px]">
          {meta.description}
        </p>

        {/* Account Details / Connection Metadata */}
        <div className="rounded-xl bg-slate-950/70 border border-slate-800/80 p-3 space-y-1.5 text-xs">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400 flex items-center gap-1.5">
              <User className="h-3 w-3 text-slate-500" />
              Account
            </span>
            <span className="font-mono text-slate-200 truncate max-w-[170px]" title={integration.account_identifier || undefined}>
              {integration.account_identifier || (isConnected ? "Connected" : "Not configured")}
            </span>
          </div>

          {isConnected && (
            <div className="flex items-center justify-between text-[11px] pt-1 border-t border-slate-800/50">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Clock className="h-3 w-3 text-slate-500" />
                Connected
              </span>
              <span className="text-slate-300">
                {integration.connected_at ? formatRelativeTime(integration.connected_at) : "Active"}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Action Footer */}
      <div className="pt-2 border-t border-slate-800/80">
        {isConnected ? (
          <button
            type="button"
            onClick={() => onDisconnectClick(integration)}
            disabled={disabled}
            className="w-full py-2 bg-slate-800 hover:bg-rose-950/60 hover:text-rose-300 hover:border-rose-800/60 text-slate-300 text-xs font-semibold rounded-xl border border-slate-700 transition-colors disabled:opacity-50"
          >
            Disconnect Service
          </button>
        ) : (
          <button
            type="button"
            onClick={() => onConnectClick(integration)}
            disabled={disabled}
            className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-md shadow-indigo-600/20 transition-all disabled:opacity-50"
          >
            Connect Service
          </button>
        )}
      </div>
    </div>
  );
}
