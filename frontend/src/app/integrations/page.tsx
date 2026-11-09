"use client";

import { useState, useMemo } from "react";
import {
  Plug,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertCircle,
  Shield,
  Layers,
} from "lucide-react";
import { IntegrationStatus } from "@/lib/types";
import {
  useIntegrations,
  useConnectIntegration,
  useDisconnectIntegration,
} from "@/lib/hooks";
import { getIntegrationMetadata } from "@/lib/utils";
import { IntegrationCard } from "@/components/integrations/integration-card";
import { IntegrationConnectDialog } from "@/components/integrations/integration-connect-dialog";
import { IntegrationDisconnectDialog } from "@/components/integrations/integration-disconnect-dialog";
import { IntegrationEmptyState } from "@/components/integrations/integration-empty-state";

type FilterTab = "all" | "connected" | "disconnected" | "communication" | "business";

export default function IntegrationsPage() {
  const {
    data: integrations,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useIntegrations();

  const connectMutation = useConnectIntegration();
  const disconnectMutation = useDisconnectIntegration();

  const [connectingIntegration, setConnectingIntegration] = useState<IntegrationStatus | null>(null);
  const [disconnectingIntegration, setDisconnectingIntegration] = useState<IntegrationStatus | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Filtered list
  const filteredIntegrations = useMemo(() => {
    if (!integrations) return [];

    return integrations.filter((item) => {
      const meta = getIntegrationMetadata(item.integration);
      const isConnected = (item.status || "").toLowerCase() === "connected";

      // Search matching
      const matchesSearch =
        item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.integration.toLowerCase().includes(searchQuery.toLowerCase()) ||
        meta.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (item.account_identifier && item.account_identifier.toLowerCase().includes(searchQuery.toLowerCase()));

      if (!matchesSearch) return false;

      // Tab matching
      if (activeTab === "connected") return isConnected;
      if (activeTab === "disconnected") return !isConnected;
      if (activeTab === "communication") return meta.category.toLowerCase().includes("communication");
      if (activeTab === "business") return meta.category.toLowerCase().includes("business");

      return true;
    });
  }, [integrations, searchQuery, activeTab]);

  const connectedCount = useMemo(() => {
    return (integrations || []).filter((i) => (i.status || "").toLowerCase() === "connected").length;
  }, [integrations]);

  const totalCount = (integrations || []).length;

  const handleConnect = async (secret: string, accountIdentifier?: string) => {
    if (!connectingIntegration) return;
    try {
      await connectMutation.mutateAsync({
        integration: connectingIntegration.integration,
        secret,
        accountIdentifier,
      });
      setFeedback({
        type: "success",
        message: `Successfully connected ${connectingIntegration.name}. Credentials registered with CredentialManager.`,
      });
      setConnectingIntegration(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to connect integration.";
      setFeedback({ type: "error", message: msg });
      throw err;
    }
  };

  const handleDisconnect = async () => {
    if (!disconnectingIntegration) return;
    try {
      await disconnectMutation.mutateAsync(disconnectingIntegration.integration);
      setFeedback({
        type: "success",
        message: `Disconnected ${disconnectingIntegration.name}. In-memory credentials revoked.`,
      });
      setDisconnectingIntegration(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to disconnect integration.";
      setFeedback({ type: "error", message: msg });
      throw err;
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-xl font-bold text-white">Integration & Tool Connectors</h2>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-950/70 text-indigo-300 border border-indigo-800/60">
              <Plug className="h-3 w-3 text-indigo-400" />
              {connectedCount} of {totalCount} Connected
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl">
            Connect external services. Credentials are bound to opaque references and auto-provisioned securely into n8n.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition-colors disabled:opacity-50"
            title="Refresh integration statuses"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin text-indigo-400" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Security Architecture Callout */}
      <div className="rounded-2xl bg-indigo-950/20 border border-indigo-900/40 p-4 flex items-start gap-3 text-xs text-indigo-200">
        <Shield className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-semibold text-indigo-300 block">
            Zero Direct External Access Architecture
          </span>
          <p className="text-indigo-200/80 leading-relaxed">
            All API calls, token exchanges, and secret provisions route through the backend Voice2Flow Agent boundary. Browser clients never communicate directly with n8n, databases, or external service APIs, ensuring zero client-side credential exposure.
          </p>
        </div>
      </div>

      {/* Feedback Alert */}
      {feedback && (
        <div
          className={`p-3.5 rounded-xl text-xs flex items-center justify-between border ${
            feedback.type === "success"
              ? "bg-emerald-950/50 border-emerald-900/60 text-emerald-300"
              : "bg-rose-950/50 border-rose-900/60 text-rose-300"
          }`}
        >
          <div className="flex items-center gap-2">
            {feedback.type === "success" ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            className="text-slate-400 hover:text-white text-xs ml-3"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Controls: Search & Tabs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pt-1">
        {/* Category Tabs */}
        <div className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-xl border border-slate-800 self-start">
          {(
            [
              { id: "all", label: "All Services" },
              { id: "connected", label: "Connected" },
              { id: "communication", label: "Communication" },
              { id: "business", label: "Business & CRM" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === tab.id
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative w-full md:w-64">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search integrations..."
            className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
          />
          <Search className="h-3.5 w-3.5 text-slate-500 absolute left-3 top-3 pointer-events-none" />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-2.5 text-xs text-slate-500 hover:text-slate-300"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Content Area */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 space-y-4 animate-pulse"
            >
              <div className="flex items-center justify-between">
                <div className="h-11 w-11 rounded-xl bg-slate-800" />
                <div className="h-5 w-20 rounded-full bg-slate-800" />
              </div>
              <div className="space-y-2">
                <div className="h-4 w-28 bg-slate-800 rounded" />
                <div className="h-3 w-48 bg-slate-800/60 rounded" />
              </div>
              <div className="h-16 bg-slate-950/60 rounded-xl" />
              <div className="h-9 bg-slate-800 rounded-xl" />
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-2xl border border-rose-900/60 bg-rose-950/20 p-8 text-center space-y-3">
          <AlertCircle className="h-8 w-8 text-rose-400 mx-auto" />
          <h3 className="text-sm font-semibold text-white">Failed to load integrations</h3>
          <p className="text-xs text-rose-300/80 max-w-md mx-auto">
            {error instanceof Error ? error.message : "An error occurred while loading integration connectors."}
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold border border-slate-700 transition-colors"
          >
            Retry Connection
          </button>
        </div>
      ) : filteredIntegrations.length === 0 ? (
        <IntegrationEmptyState
          title={searchQuery ? "No matching integrations" : "No integrations available"}
          description={
            searchQuery
              ? `No integrations found matching "${searchQuery}". Try adjusting your search or filter.`
              : "No integration connectors are currently registered on this tenant."
          }
          onRefresh={() => refetch()}
          isRefreshing={isFetching}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredIntegrations.map((item) => (
            <IntegrationCard
              key={item.integration}
              integration={item}
              onConnectClick={(target) => setConnectingIntegration(target)}
              onDisconnectClick={(target) => setDisconnectingIntegration(target)}
              disabled={connectMutation.isPending || disconnectMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Connect Dialog */}
      {connectingIntegration && (
        <IntegrationConnectDialog
          integration={connectingIntegration}
          onClose={() => setConnectingIntegration(null)}
          onConnect={handleConnect}
          loading={connectMutation.isPending}
        />
      )}

      {/* Disconnect Dialog */}
      {disconnectingIntegration && (
        <IntegrationDisconnectDialog
          integration={disconnectingIntegration}
          onClose={() => setDisconnectingIntegration(null)}
          onDisconnect={handleDisconnect}
          loading={disconnectMutation.isPending}
        />
      )}
    </div>
  );
}
