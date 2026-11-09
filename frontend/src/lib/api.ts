/**
 * Centralized Typed API Client for Voice2Flow FastAPI Backend.
 */

import {
  AgentChatResponse,
  AgentConfirmResponse,
  AutomationDetail,
  AutomationSummary,
  DashboardStats,
  IntegrationStatus,
  IntegrationConnectResult,
  IntegrationDisconnectResult,
  AuditEvent,
  ExecutionRecord,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Development default headers (customizable per session in Phase 11 MVP)
let currentOrgId = "org_demo_001";
let currentUserId = "user_demo_001";
let currentPermissions = "crm.read,crm.write,gmail.send,slack.send";

export function setTenantContext(orgId: string, userId: string, permissions: string[]) {
  currentOrgId = orgId;
  currentUserId = userId;
  currentPermissions = permissions.join(",");
}

export function getTenantHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-Organization-Id": currentOrgId,
    "X-User-Id": currentUserId,
    "X-User-Permissions": currentPermissions,
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errJson = await res.json();
      errorDetail = errJson.error || errJson.detail || errorDetail;
    } catch {
      // fallback to status text
    }
    throw new Error(errorDetail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // ─── HEALTH ──────────────────────────────────────────────
  async getHealth(): Promise<{ status: string; service: string }> {
    const res = await fetch(`${API_BASE_URL}/api/healthz`, {
      headers: getTenantHeaders(),
    });
    return handleResponse(res);
  },

  // ─── AGENT ───────────────────────────────────────────────
  async sendAgentChat(message: string, conversationId?: string): Promise<AgentChatResponse> {
    const res = await fetch(`${API_BASE_URL}/api/agent/chat`, {
      method: "POST",
      headers: getTenantHeaders(),
      body: JSON.stringify({ message, conversation_id: conversationId }),
    });
    return handleResponse<AgentChatResponse>(res);
  },

  async confirmAgentAction(runId: string, conversationId: string, approved: boolean): Promise<AgentConfirmResponse> {
    const res = await fetch(`${API_BASE_URL}/api/agent/confirm`, {
      method: "POST",
      headers: getTenantHeaders(),
      body: JSON.stringify({ run_id: runId, conversation_id: conversationId, approved }),
    });
    return handleResponse<AgentConfirmResponse>(res);
  },

  // ─── AUTOMATIONS ─────────────────────────────────────────
  async listAutomations(): Promise<AutomationSummary[]> {
    const res = await fetch(`${API_BASE_URL}/api/automations`, {
      headers: getTenantHeaders(),
    });
    return handleResponse<AutomationSummary[]>(res);
  },

  async getAutomation(id: string): Promise<AutomationDetail> {
    const res = await fetch(`${API_BASE_URL}/api/automations/${id}`, {
      headers: getTenantHeaders(),
    });
    return handleResponse<AutomationDetail>(res);
  },

  // ─── INTEGRATIONS ────────────────────────────────────────
  async listIntegrations(): Promise<IntegrationStatus[]> {
    const res = await fetch(`${API_BASE_URL}/api/integrations`, {
      headers: getTenantHeaders(),
    });
    return handleResponse<IntegrationStatus[]>(res);
  },

  async connectIntegration(
    integration: string,
    secret: string,
    accountIdentifier?: string
  ): Promise<IntegrationConnectResult> {
    const res = await fetch(`${API_BASE_URL}/api/integrations/${integration}/connect`, {
      method: "POST",
      headers: getTenantHeaders(),
      body: JSON.stringify({ secret, account_identifier: accountIdentifier }),
    });
    return handleResponse<IntegrationConnectResult>(res);
  },

  async disconnectIntegration(integration: string): Promise<IntegrationDisconnectResult> {
    const res = await fetch(`${API_BASE_URL}/api/integrations/${integration}/disconnect`, {
      method: "POST",
      headers: getTenantHeaders(),
    });
    return handleResponse<IntegrationDisconnectResult>(res);
  },

  // ─── STATS & OBSERVABILITY ───────────────────────────────
  async getDashboardStats(): Promise<DashboardStats> {
    const res = await fetch(`${API_BASE_URL}/api/dashboard/stats`, {
      headers: getTenantHeaders(),
    });
    return handleResponse<DashboardStats>(res);
  },

  async listActivity(limit = 50, offset = 0): Promise<AuditEvent[]> {
    const res = await fetch(`${API_BASE_URL}/api/activity?limit=${limit}&offset=${offset}`, {
      headers: getTenantHeaders(),
    });
    return handleResponse<AuditEvent[]>(res);
  },

  async listExecutions(limit = 50, offset = 0): Promise<ExecutionRecord[]> {
    const res = await fetch(`${API_BASE_URL}/api/executions?limit=${limit}&offset=${offset}`, {
      headers: getTenantHeaders(),
    });
    return handleResponse<ExecutionRecord[]>(res);
  },
};
