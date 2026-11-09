export function formatRelativeTime(dateString?: string | null): string {
  if (!dateString) return "—";
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    if (diffMs < 0 || isNaN(diffMs)) {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    const diffSecs = Math.floor(diffMs / 1000);
    if (diffSecs < 60) return "just now";
    const diffMins = Math.floor(diffSecs / 60);
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return "—";
  }
}

const SENSITIVE_KEY_PATTERN = /(token|secret|password|key|auth|credential|bearer)/i;

/**
 * Strips or redacts any sensitive credential fields before display.
 */
export function sanitizeParameters(params: Record<string, unknown> | null | undefined): Record<string, unknown> {
  if (!params || typeof params !== "object") return {};
  const sanitized: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(params)) {
    if (SENSITIVE_KEY_PATTERN.test(k)) {
      sanitized[k] = "[REDACTED]";
    } else if (v && typeof v === "object" && !Array.isArray(v)) {
      sanitized[k] = sanitizeParameters(v as Record<string, unknown>);
    } else {
      sanitized[k] = v;
    }
  }
  return sanitized;
}

/**
 * Converts backend error codes and messages into safe, user-friendly copy.
 */
export function formatAgentErrorMessage(error: unknown, errorCode?: string | null): string {
  if (errorCode === "PERMISSION_DENIED") {
    return "You don't have permission to perform that action. Contact your organization administrator for access.";
  }
  if (errorCode === "HIGH_RISK_BLOCKED") {
    return "This action is classified as high-risk and blocked by safety policies from autonomous execution.";
  }
  if (errorCode === "AUTOMATION_NOT_FOUND") {
    return "The requested automation could not be found.";
  }
  if (errorCode === "AUTOMATION_AMBIGUOUS") {
    return "Multiple matching automations were found. Please specify the exact automation name.";
  }
  if (errorCode === "AUTOMATION_CREATION_FAILED") {
    return "Could not create the automation. Please check your prompt requirements.";
  }
  if (errorCode === "DATABASE_UNAVAILABLE") {
    return "The Voice2Flow persistence service is temporarily unavailable. Please try again in a moment.";
  }

  const rawMessage = error instanceof Error ? error.message : typeof error === "string" ? error : "";

  if (rawMessage.includes("404") || rawMessage.toLowerCase().includes("no pending operation found")) {
    return "This confirmation is no longer valid or has already expired.";
  }
  if (rawMessage.includes("409") || rawMessage.toLowerCase().includes("does not match the pending operation")) {
    return "This confirmation has already been processed or the operation ID is no longer active.";
  }
  if (rawMessage.includes("403") || rawMessage.toLowerCase().includes("permission")) {
    return "You do not have permission to execute this operation.";
  }
  if (rawMessage.includes("503") || rawMessage.toLowerCase().includes("service unavailable")) {
    return "The Agent service is currently unavailable. Please try again shortly.";
  }
  if (rawMessage.toLowerCase().includes("failed to fetch") || rawMessage.toLowerCase().includes("network")) {
    return "Unable to reach the Voice2Flow Agent API. Please verify your connection or backend status.";
  }

  // Safe fallback without raw stack traces
  if (rawMessage && !rawMessage.includes("Traceback") && !rawMessage.includes("File \"")) {
    return rawMessage;
  }
  return "I couldn't complete that request. Please try again or rephrase your prompt.";
}

/**
 * Provides user-facing copy and guidance for supported integrations.
 */
export function getIntegrationMetadata(key: string): {
  category: string;
  description: string;
  authTypeLabel: string;
  providerAuth: "oauth2" | "bot_token" | "api_key" | "secret";
  secretPlaceholder: string;
  secretHelp: string;
} {
  const norm = key.toLowerCase();
  switch (norm) {
    case "gmail":
      return {
        category: "Communication",
        description: "Send automated alerts, customer follow-ups, and notifications via Gmail.",
        authTypeLabel: "Google OAuth 2.0",
        providerAuth: "oauth2",
        secretPlaceholder: "Paste OAuth tokens JSON or access token...",
        secretHelp: "Connect directly with Google OAuth 2.0. Tokens are encrypted in CredentialManager and provisioned into n8n under gmailOAuth2.",
      };
    case "slack":
      return {
        category: "Communication",
        description: "Post messages, channel notifications, and approval alerts to Slack workspaces.",
        authTypeLabel: "Bot User OAuth Token",
        providerAuth: "bot_token",
        secretPlaceholder: "xoxb-... (Bot User OAuth Token)",
        secretHelp: "Enter your Slack Bot Token (starts with xoxb-). Requires chat:write and channels:read scopes. Provisioned into n8n as slackApi.",
      };
    case "crm":
      return {
        category: "Business & CRM",
        description: "Read and write customer contacts, orders, and support tickets in your CRM.",
        authTypeLabel: "Internal API Key",
        providerAuth: "api_key",
        secretPlaceholder: "Enter CRM API key (e.g. demo-crm-api-key)...",
        secretHelp: "Voice2Flow Built-in Demo CRM API key. Provisioned into n8n as httpHeaderAuth with header X-API-Key.",
      };
    default:
      return {
        category: "Services",
        description: "Connect external tools and services to Voice2Flow.",
        authTypeLabel: "API Secret",
        providerAuth: "secret",
        secretPlaceholder: "Enter credential secret...",
        secretHelp: "Credentials are bound to opaque references and stored securely.",
      };
  }
}

/**
 * Calculates human-readable duration between started and completed timestamps.
 */
export function formatDuration(startedAt?: string | null, completedAt?: string | null): string {
  if (!startedAt) return "—";
  if (!completedAt) return "Running";
  try {
    const start = new Date(startedAt).getTime();
    const end = new Date(completedAt).getTime();
    const diffMs = end - start;
    if (isNaN(diffMs) || diffMs < 0) return "—";
    if (diffMs < 1000) return `${diffMs}ms`;
    if (diffMs < 60000) return `${(diffMs / 1000).toFixed(1)}s`;
    const mins = Math.floor(diffMs / 60000);
    const secs = Math.floor((diffMs % 60000) / 1000);
    return `${mins}m ${secs}s`;
  } catch {
    return "—";
  }
}

/**
 * Translates an audit event and its sanitized metadata into safe human-readable copy.
 * Under no circumstances does this render raw secrets or arbitrary JSON payloads.
 */
export function getSafeEventSummary(
  eventType: string,
  mode?: string | null,
  status?: string | null,
  metadata?: Record<string, unknown> | null
): string {
  const normType = (eventType || "").toUpperCase();
  const safeMeta = metadata || {};

  switch (normType) {
    case "AGENT_REQUEST":
      if (typeof safeMeta.message_length === "number") {
        return `User initiated request (${safeMeta.message_length} chars)`;
      }
      return "User initiated agent request";

    case "PLAN_CREATED":
      if (typeof safeMeta.step_count === "number") {
        return `Generated execution plan with ${safeMeta.step_count} step${safeMeta.step_count === 1 ? "" : "s"}`;
      }
      return `Generated execution plan for ${mode || "request"}`;

    case "AUTOMATION_CREATED":
      return "Created automation workflow";

    case "AUTOMATION_MODIFIED":
      return "Modified automation workflow";

    case "EXECUTION_STARTED":
      return `Started execution in ${mode || "agent"} mode`;

    case "EXECUTION_COMPLETED":
      return "Execution completed successfully";

    case "EXECUTION_FAILED":
      return "Execution encountered an error";

    default:
      return normType.replace(/_/g, " ").toLowerCase();
  }
}

