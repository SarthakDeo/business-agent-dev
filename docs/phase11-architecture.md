# Phase 11 — Frontend & API Boundary Architecture

## 1. Overview

Phase 11 introduces a web application layer on top of the verified Phase 1–10 Gnani Business Agent core:
- **Phase 11A:** Next.js frontend foundation (`frontend/`)
- **Phase 11B:** FastAPI backend HTTP boundary (`backend/api/`)

The architecture preserves all security, permission, and persistence guarantees established in earlier phases. The browser interacts exclusively with the FastAPI layer over REST; it never connects directly to PostgreSQL, n8n, Gemini, or Prisma.

---

## 2. Next.js Frontend Structure (`frontend/`)

```text
frontend/
├── package.json               # Next.js 15.5, React 19, TailwindCSS, @tanstack/react-query, lucide-react
├── tsconfig.json              # Strict TypeScript configuration with @/* path aliases
├── next.config.ts             # Next.js configuration
├── postcss.config.mjs         # PostCSS configuration for Tailwind
├── tailwind.config.ts         # Tailwind CSS styling tokens
└── src/
    ├── app/
    │   ├── layout.tsx         # Root app shell: Sidebar + Header + QueryClientProvider
    │   ├── page.tsx           # Default redirect to /dashboard
    │   ├── dashboard/page.tsx # KPI summary cards & quick launch console
    │   ├── agent/page.tsx     # Interactive chat feed & Human Approval ConfirmationCard
    │   ├── automations/page.tsx # Canonical workflow registry table
    │   ├── integrations/page.tsx # Integration connectors & connection modal
    │   ├── activity/page.tsx  # Tamper-evident audit event log stream
    │   └── executions/page.tsx # Tool execution & automation history
    ├── components/layout/
    │   ├── sidebar.tsx        # Navigation sidebar with route links & status
    │   └── header.tsx         # Tenant badge, database indicator, and console header
    ├── lib/
    │   ├── api.ts             # Centralized typed fetch client with development headers
    │   ├── types.ts           # TypeScript interfaces matching backend Pydantic models
    │   └── query-client.tsx   # React Query Client provider configuration
    └── styles/
        └── globals.css        # Tailwind styles & theme variables
```

---

## 3. FastAPI Backend Structure (`backend/api/`)

```text
backend/api/
├── __init__.py
├── app.py                     # ASGI FastAPI app, CORS middleware, exception handlers
├── dependencies.py            # TenantContext extraction, PostgreSQL injection, Session bridging
├── schemas.py                 # Pydantic request and response models
└── routes/
    ├── __init__.py
    ├── agent.py               # POST /api/agent/chat, POST /api/agent/confirm
    ├── automations.py         # GET /api/automations, GET /api/automations/{id}
    ├── integrations.py        # GET /api/integrations, POST /connect, POST /disconnect
    ├── dashboard.py           # GET /api/dashboard/stats
    ├── activity.py            # GET /api/activity
    └── executions.py          # GET /api/executions
```

---

## 4. API Endpoints

All endpoints require development tenant headers:
- `X-Organization-Id: <org_id>`
- `X-User-Id: <user_id>`
- `X-User-Permissions: <perm1,perm2>` (optional, comma-separated)

| Method | Path | Description | Response Model |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/healthz` | Service health check | `{"status": "ok", "service": "gnani-api"}` |
| `POST` | `/api/agent/chat` | Send user message to Agent | `AgentChatResponse` |
| `POST` | `/api/agent/confirm` | Approve or reject pending action | `AgentConfirmResponse` |
| `GET` | `/api/automations` | List automations for tenant | `list[AutomationSummaryResponse]` |
| `GET` | `/api/automations/{id}` | Inspect canonical workflow details | `AutomationDetailResponse` |
| `GET` | `/api/integrations` | List supported integration statuses | `list[IntegrationStatusResponse]` |
| `POST` | `/api/integrations/{integ}/connect` | Connect integration with secret | `IntegrationConnectResponse` |
| `POST` | `/api/integrations/{integ}/disconnect` | Disconnect and revoke integration | `IntegrationDisconnectResponse` |
| `GET` | `/api/dashboard/stats` | Aggregate dashboard KPI metrics | `DashboardStatsResponse` |
| `GET` | `/api/activity` | List sanitized audit events | `list[AuditEventResponse]` |
| `GET` | `/api/executions` | List execution history records | `list[ExecutionResponse]` |

---

## 5. Development Tenant Context Notice

> **IMPORTANT:** `X-Organization-Id`, `X-User-Id`, and `X-User-Permissions` are development/demo context headers and are not production authentication.

- For Phase 11 MVP, these headers allow testing multi-tenancy, cross-tenant isolation, and permission checks from the browser and API clients.
- In production, these headers will be replaced by cryptographic JWT/session tokens verified by backend authentication middleware without changing route business logic.

---

## 6. PostgreSQL Dependency & Failure Behavior

- The FastAPI application defaults to `PostgresStateStore` with the runtime DSN (`POSTGRES_DSN` or `postgresql://gnani_test:gnani_test_password@localhost:5432/gnani_test`).
- **Zero Silent Fallback:** If PostgreSQL is unreachable, the API fails closed with HTTP 503 `DATABASE_UNAVAILABLE`. It never silently switches to SQLite in runtime mode.

---

## 7. Confirmation Flow

When an operation involves medium-risk tools or automation creation/modification:
1. `POST /api/agent/chat` returns `status: "awaiting_confirmation"` with `pending_confirmation: { summary, risk, steps }`.
2. The frontend Agent view renders an interactive banner with **Approve** and **Reject** buttons.
3. User clicks an action, calling `POST /api/agent/confirm` with `run_id`, `conversation_id`, and `approved: true/false`.
4. The backend verifies the session context matches the active user and tenant.
5. If approved, `agent.resume_confirmation()` executes the pending operation. If rejected, it cancels execution cleanly without side effects.
6. Once resolved, the pending state is cleared, preventing replay attempts.

---

## 8. Security Boundary

- **No Browser Direct DB Access:** The browser cannot access port 5432 or issue SQL queries.
- **No Browser Direct n8n Access:** The browser cannot access port 5678 or call n8n endpoints directly.
- **Secret Redaction:** Raw secrets received during `POST /connect` are passed to `CredentialManager` and held in-memory; they are never logged, serialized into PostgreSQL, or returned to the browser.
- **Tenant Scoping:** All state store queries strictly include `WHERE organization_id = %s`.
- **Sanitized Errors:** Unhandled exceptions return generic 500 responses with correlation IDs; Python tracebacks and database connection details are never leaked to the browser.

---

## 9. How to Start

### Start FastAPI Backend
```bash
# In project root with active .venv:
python -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload
```

### Start Next.js Frontend
```bash
# In frontend/ directory:
cd frontend
npm run dev
# Open browser at http://localhost:3000
```

---

## 10. Known Development-Only Limitations

- **Session Context Storage:** For Phase 11 MVP, conversation and pending confirmation objects (`ConversationContext`) are bridged in-memory in `backend/api/dependencies.py` keyed by `(organization_id, user_id, conversation_id)`. In a distributed multi-worker deployment, this session state would be backed by Redis or PostgreSQL session records.
- **Development Header Authentication:** The frontend currently passes static headers (`org_demo_001`, `user_demo_001`) from `api.ts`.

---

## 11. Phase 11D — Agent UI Architecture

### 11.1 Component Breakdown (`frontend/src/components/agent/`)

```text
frontend/src/components/agent/
├── agent-shell.tsx          # Top-level conversation controller, state manager & scroll orchestrator
├── chat-message.tsx         # Message bubble with mode pill, status badge, run ID & automation links
├── chat-input.tsx           # Auto-resizing textarea with keyboard shortcuts (Enter / Shift+Enter)
├── confirmation-card.tsx    # Human-in-the-loop security boundary approval card
├── confirmation-details.tsx # Collapsible execution plan breakdown with parameter sanitization
├── starter-prompts.tsx      # Welcome screen starter chips covering ASK, DO, and AUTOMATE
├── mode-badge.tsx           # Visual indicator for ASK, DO, and AUTOMATE with descriptive subtext
├── status-badge.tsx         # Execution status indicators (completed, awaiting_confirmation, etc.)
├── typing-indicator.tsx     # Animated pulse indicator while Agent coordinates with tools
└── error-message.tsx        # User-friendly error alert with sanitized messaging and retry action
```

### 11.2 State Management & Conversation Lifecycle
- **Conversation Continuity:** `conversation_id` is generated by the backend on the first request and preserved in client state across subsequent messages.
- **Tenant Context:** Requests strictly transmit `X-Organization-Id`, `X-User-Id`, and `X-User-Permissions` via `getTenantHeaders()`.
- **Query Cache Invalidation:** Successful messages and confirmations automatically invalidate React Query caches for `dashboard-stats`, `recent-activity`, and `recent-executions`.
- **Confirmation Flow:**
  1. If backend returns `status === "awaiting_confirmation"`, `pending_confirmation` metadata is stored in `activePending` state.
  2. The input field is safely locked with explicit helper text.
  3. The user inspects sanitized parameters and selects **Approve & Execute** or **Reject Action**.
  4. The frontend calls `POST /api/agent/confirm`. Upon resolution, the pending state is cleared and normal input is restored.
- **Automation Linkage:** When an automation is created in `AUTOMATE` mode, the message displays the deployed n8n workflow ID and provides a direct navigation link to `/automations/${automation_id}`.

---

## 12. Phase 11E — Automation Management UI Architecture

### 12.1 Pages & Routes
- **`/automations` (`frontend/src/app/automations/page.tsx`):**
  - Displays all persistent automations for the authenticated tenant.
  - Client-side search matching across name, automation ID, and tool names.
  - Status filter tabs: `All`, `Active`, `Updated`, `Inactive`.
  - Responsive grid rendering `<AutomationCard />` with step counts, n8n references, and relative timestamps.
  - "+ Create with Gnani" CTA linking to `/agent`.
  - Empty state with quick starter prompts when no automations exist.
- **`/automations/[id]` (`frontend/src/app/automations/[id]/page.tsx`):**
  - Full inspection view of a single canonical automation.
  - Back navigation to `/automations`.
  - Live status badge, timestamps, and tenant correlation identifiers.
  - Visual DAG timeline rendering trigger parameters and sequential tool steps.
  - "Modify with Gnani" CTA routing to `/agent?prompt=Modify automation <name> to `.
  - Graceful 404 handling when an automation is missing or belongs to another tenant.

### 12.2 Component Breakdown (`frontend/src/components/automations/`)
```text
frontend/src/components/automations/
├── automation-card.tsx         # List view card with metadata and link to detail page
├── automation-status.tsx       # Status badge for Active, Created, Updated, Paused
├── automation-trigger.tsx      # Trigger node card with type-specific icon and sanitized parameters
├── automation-step.tsx         # Sequential action step node with parameter inspector
├── automation-workflow.tsx     # Vertical DAG timeline orchestrator connecting trigger to steps
├── automation-search.tsx       # Search input with clear button and status filter pills
└── automation-empty-state.tsx  # Empty console with actions to open Agent
```

### 12.3 API Integration
- `GET /api/automations`: Consumed by `useAutomationsList()` to populate the automation registry table/grid.
- `GET /api/automations/{id}`: Consumed by `useAutomationDetail(id)` to retrieve canonical workflow metadata.

### 12.4 Security Boundary & Parameter Sanitization
- **No Direct n8n Access:** The browser cannot access n8n on port 5678 or call n8n REST endpoints directly.
- **No Direct Database Access:** The browser cannot query PostgreSQL directly on port 5432.
- **Secret Redaction:** Parameter display passes through `sanitizeParameters()`. Credentials, API tokens, passwords, and secrets are strictly redacted. Dynamic references (e.g. `{{trigger.customer_id}}`) remain inspectable for debugging.
- **Why Direct n8n Manipulation is Omitted:** The frontend is purely an inspection and navigation layer. In Gnani's architecture, automation creation and modification must always route through `Agent.run()` / `Agent.resume_confirmation()` to ensure strict permission checks (`check_permissions`), risk classification (`evaluate_confirmation`), and human approval gates are enforced. Direct frontend mutations would bypass these critical security gates.

---

## 13. Phase 11F — Integration Management UI Architecture

### 13.1 Pages & Routes
- **`/integrations` (`frontend/src/app/integrations/page.tsx`):**
  - Displays all supported integration connectors (Gmail, Slack, CRM) and their active connection status for the authenticated tenant.
  - Header with title, descriptive subtitle, connection counter badge (`X of Y Connected`), and refetch action button with loading spinner.
  - Category filter tabs: `All Services`, `Connected`, `Communication`, `Business & CRM`.
  - Client-side search input filtering across service names, keys, categories, and account identifiers.
  - Architecture callout emphasizing the Zero Direct External Access model.
  - Responsive card grid rendering `<IntegrationCard />` with dynamic icons, status badges, account labels, and relative timestamps.
  - Inline feedback alerts for successful connections, disconnections, and error handling.
  - Connect and Disconnect modal workflows with input scrubbing and error boundaries.

### 13.2 Component Breakdown (`frontend/src/components/integrations/`)
```text
frontend/src/components/integrations/
├── integration-card.tsx               # Service card with icon, status badge, auth type, account label & action trigger
├── integration-status.tsx             # Reusable status badge (Connected [green] / Disconnected [slate])
├── integration-connect-dialog.tsx      # Secure credential entry modal with masked input, eye toggle & scrubbing
├── integration-disconnect-dialog.tsx   # Impact-warning confirmation modal before credential revocation
└── integration-empty-state.tsx         # Filter mismatch or empty state with retry/refresh action
```

### 13.3 API Integration & Query Lifecycle
- **`GET /api/integrations`:**
  - Consumed by `useIntegrations()` hook (`frontend/src/lib/hooks.ts`).
  - Returns `list[IntegrationStatusResponse]` containing `integration`, `name`, `status`, `account_identifier`, and `connected_at`.
- **`POST /api/integrations/{integration}/connect`:**
  - Consumed by `useConnectIntegration()` mutation hook.
  - Payload: `{ "secret": str, "account_identifier": Optional[str] }`.
  - Returns `IntegrationConnectResponse` (`status="connected"`, `integration`, `account_identifier`).
  - Automatically invalidates `integrations`, `integration-health`, and `dashboard-stats` query keys.
- **`POST /api/integrations/{integration}/disconnect`:**
  - Consumed by `useDisconnectIntegration()` mutation hook.
  - Revokes credential reference in `CredentialManager` and updates connection record to `disconnected`.
  - Returns `IntegrationDisconnectResponse` (`status="disconnected"`, `integration`).
  - Automatically invalidates `integrations`, `integration-health`, and `dashboard-stats` query keys.

### 13.4 Security & Credential Isolation Guarantees
- **No Client-Side Credential Storage:** Secrets are never stored in `localStorage`, `sessionStorage`, cookies, IndexedDB, or component state across unmounts.
- **Immediate Input Scrubbing:** `IntegrationConnectDialog` scrubs secret state immediately upon submission or dialog cancellation.
- **Zero Direct Browser Calls:** The browser communicates exclusively with FastAPI (`http://localhost:8000`). It has zero access to n8n (port 5678), PostgreSQL (port 5432), or external provider APIs (Google, Slack, CRM).
- **Opaque Reference Provisioning:** Credentials are encrypted and held in-memory via `CredentialManager` as opaque `cred_...` references. When an n8n client is active, credentials are provisioned directly to n8n via server-to-server calls and registered in the internal mapping table.
- **Strict Tenant Contract:** All integration requests enforce `X-Organization-Id` and `X-User-Id`. Legacy `X-Tenant-ID` headers are rejected with HTTP 400.

---

## 14. Phase 11G — Activity & Execution Management UI Architecture

### 14.1 Pages & Routes
- **`/activity` (`frontend/src/app/activity/page.tsx`):**
  - Observability timeline rendering immutable audit records (`gnani_audit_events`).
  - Category filter tabs: `All Activity`, `Requests`, `Plans`, `Automations`, `Executions`.
  - Client-side search input matching event types, modes, statuses, run IDs, user IDs, and safe event summaries.
  - Bounded pagination controls (`limit=25`, `offset`) with Previous/Next controls.
  - Security architecture callout emphasizing read-only audit isolation and pre-storage secret redaction.
- **`/executions` (`frontend/src/app/executions/page.tsx`):**
  - Operational execution telemetry table displaying direct tool actions and automated workflow executions (`gnani_executions`).
  - Status filter tabs: `All Status`, `Completed`, `Failed`, `Running`.
  - Mode filters: `All Modes`, `ASK`, `DO`, `AUTOMATE`.
  - Client-side search matching execution IDs, modes, statuses, automation IDs, request IDs, user IDs, and error codes.
  - Duration calculation via `formatDuration(started_at, completed_at)`.
  - Direct navigation links to `/automations/${id}` when an automation ID exists on the record.
  - Inspection modal (`ExecutionDetailModal`) allowing operators to inspect safe execution context, duration, and error codes with zero secret exposure.

### 14.2 Component Breakdown
```text
frontend/src/components/activity/
├── activity-event.tsx          # Individual audit event card with type-specific icons, mode pills, and safe summaries
├── activity-filters.tsx        # Tabbed event filter and instant search input
├── activity-empty-state.tsx    # Informative fallback when no activity records exist or match filters
└── activity-list.tsx           # Container rendering the filtered audit stream

frontend/src/components/executions/
├── execution-row.tsx           # Individual execution card with status, mode, duration, automation link, and details action
├── execution-status.tsx        # Reusable status badge (Completed [emerald], Failed [rose], Running [blue])
├── execution-filters.tsx       # Status tabs, mode filter buttons, and instant search input
├── execution-empty-state.tsx   # Informative fallback when no execution records exist or match filters
└── execution-detail-modal.tsx  # Accessible modal dialog displaying execution duration, provenance, and sanitized metadata
```

### 14.3 API Integration & React Query Hooks
- **`GET /api/activity?limit={limit}&offset={offset}`:**
  - Consumed by `useActivity(limit, offset)` in `frontend/src/lib/hooks.ts`.
  - Returns `list[AuditEventResponse]` (`id`, `organization_id`, `user_id`, `request_id`, `run_id`, `event_type`, `mode`, `action`, `status`, `metadata`, `created_at`).
- **`GET /api/executions?limit={limit}&offset={offset}`:**
  - Consumed by `useExecutions(limit, offset)` in `frontend/src/lib/hooks.ts`.
  - Returns `list[ExecutionResponse]` (`id`, `organization_id`, `user_id`, `automation_id`, `request_id`, `mode`, `status`, `error_code`, `metadata`, `started_at`, `completed_at`).
- **Dashboard Observability Integration:**
  - The dashboard (`/dashboard`) consumes bounded recent queries via `useRecentActivity(5)` and `useRecentExecutions(5)`.
  - Header actions on both dashboard sections navigate directly to `/activity` and `/executions` for comprehensive, paginated audit trails.

### 14.4 Observability Security & Redaction Guarantees
- **Read-Only Observability:** Neither `/activity` nor `/executions` contains mutation actions. Records are strictly observational historical telemetry.
- **Storage-Level Redaction:** Credentials and secrets (`secret`, `token`, `password`, `api_key`, `authorization`) are sanitized via `_safe_json` and `_safe_text` prior to persistence in PostgreSQL.
- **No Raw Payload Dumps:** The UI never dumps raw JSON or unredacted objects. Safe summaries (`getSafeEventSummary`) and explicit fields are used.
- **Strict Tenant Isolation:** All telemetry queries strictly enforce `X-Organization-Id` and `X-User-Id`. Cross-tenant queries are blocked at the database layer. Legacy `X-Tenant-ID` headers are rejected with HTTP 400.
- **Zero Direct Browser Connections:** Browser clients never communicate directly with PostgreSQL (5432) or n8n (5678). All telemetry flows exclusively through the FastAPI gateway.


