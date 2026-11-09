/**
 * TypeScript contracts mirroring Voice2Flow FastAPI responses.
 */

export interface PendingConfirmationInfo {
  summary: string;
  risk: string;
  steps: Array<Record<string, unknown>>;
  mode?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  mode?: "ASK" | "DO" | "AUTOMATE" | string;
  status?: "completed" | "awaiting_confirmation" | "error" | "blocked" | string;
  runId?: string;
  conversationId?: string;
  timestamp: string;
  pendingConfirmation?: PendingConfirmationInfo | null;
  executionResults?: Record<string, unknown>;
  automationId?: string;
  error?: string | null;
  errorCode?: string | null;
}

export interface AgentChatResponse {
  response: string;
  mode: string;
  status: string;
  run_id: string;
  conversation_id: string;
  plan: Record<string, unknown>;
  pending_confirmation?: PendingConfirmationInfo | null;
  execution_results: Record<string, unknown>;
  error?: string | null;
  error_code?: string | null;
}

export interface AgentConfirmResponse {
  response: string;
  status: string;
  run_id: string;
  conversation_id: string;
  execution_results: Record<string, unknown>;
  error?: string | null;
  error_code?: string | null;
}

export interface AutomationTrigger {
  type: string;
  parameters?: Record<string, unknown>;
}

export interface AutomationStep {
  id: string;
  tool: string;
  parameters?: Record<string, unknown>;
  description?: string;
}

export interface CanonicalWorkflow {
  name?: string;
  description?: string;
  mode?: string;
  trigger?: AutomationTrigger;
  steps?: AutomationStep[];
}

export interface AutomationSummary {
  id: string;
  name: string;
  status: string;
  n8n_workflow_id: string;
  step_count: number;
  created_at: string;
  updated_at: string;
}

export interface AutomationDetail {
  id: string;
  organization_id: string;
  name: string;
  status: string;
  n8n_workflow_id: string;
  canonical_workflow: CanonicalWorkflow;
  created_at: string;
  updated_at: string;
}

export interface IntegrationStatus {
  integration: string;
  name: string;
  status: string;
  account_identifier?: string | null;
  connected_at?: string | null;
}

export interface IntegrationConnectPayload {
  secret: string;
  account_identifier?: string;
}

export interface IntegrationConnectResult {
  status: string;
  integration: string;
  account_identifier?: string | null;
}

export interface IntegrationDisconnectResult {
  status: string;
  integration: string;
}

export interface DashboardStats {
  automations: number;
  active_automations: number;
  integrations: number;
  recent_executions: number;
  recent_errors: number;
}

export interface AuditEvent {
  id: string;
  organization_id: string;
  user_id?: string | null;
  request_id?: string | null;
  run_id?: string | null;
  event_type: string;
  mode?: string | null;
  action?: string | null;
  status?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ExecutionRecord {
  id: string;
  organization_id: string;
  user_id?: string | null;
  automation_id?: string | null;
  request_id?: string | null;
  mode: string;
  status: string;
  error_code?: string | null;
  metadata: Record<string, unknown>;
  started_at: string;
  completed_at?: string | null;
}

export interface ApiError {
  error: string;
  error_code: string;
  status: string;
  request_id?: string | null;
}
