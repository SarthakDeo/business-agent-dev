# Voice2Flow AI Business Agent

> **Prisma hears. Gemini plans. Your agent decides. n8n acts. PostgreSQL remembers.**

The **Voice2Flow AI Business Agent** is an enterprise-grade autonomous AI orchestration and workflow automation platform. It bridges human speech and natural-language intent with deterministic business execution across CRM systems, Slack channels, and Gmail.

The platform guarantees safety, tenant isolation, and auditability by treating generative AI outputs as **untrusted plan proposals**, verifying permissions deterministically, enforcing human-in-the-loop approval gates for medium/high-risk actions, and compiling canonical workflows into isolated n8n executions backed by PostgreSQL.

---

## Architecture Overview

```text
                            USER / VOICE
                                 │
                                 ▼
                             Prisma STT
                                 │
                                 ▼
                        Next.js Web Frontend
                      (Dashboard, Agent Console,
                      Automations, Integrations,
                        Activity & Executions)
                                 │
                          (HTTP / JSON REST)
                                 │
                                 ▼
                          FastAPI Gateway
                     (Tenant Context, CORS, Auth)
                                 │
                                 ▼
                        Voice2Flow Agent Core
                  (Planner, Validator, Permissions,
                    Risk Evaluation, Confirmation)
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
 Integration Manager      Workflow Compiler      PostgresStateStore
(Opaque Credentials)       (AST → n8n JSON)       (Tenant Scoped)
         │                       │                       │
         ▼                       ▼                       ▼
   External Tools               n8n               PostgreSQL DB
 (Gmail, Slack, CRM)      (Port 5678 Engine)      (Port 5432 DB)
```

---

## Core Functionalities

### 1. Unified ASK / DO / AUTOMATE Execution Modes
- **`ASK` (Read-Only Insights):** Executes safe queries against connected services (e.g., *"How many delayed orders do we have?"*) without creating side effects or persistent workflows.
- **`DO` (Single-Action Execution):** Dispatches real-time operational commands (e.g., *"Send a Slack update to #logistics about order #1042"*). Medium-risk operations trigger a human approval card before any execution occurs.
- **`AUTOMATE (CREATE)` (Workflow Synthesis):** Converts natural language into a structured canonical DAG workflow with triggers and sequential action steps, compiles it into n8n JSON, provisions opaque credentials, activates the workflow in n8n, and stores it in PostgreSQL.
- **`AUTOMATE (MODIFY)` (In-Place Evolution):** Modifies existing automations (e.g., *"Add a customer email step to the ticket complaint workflow"*) by updating the canonical AST and re-deploying in place to the exact same n8n workflow ID, preserving persistence identity.

### 2. Multi-Layered Security & Human-in-the-Loop Confirmation
- **Untrusted Plan Boundary:** LLM output is strictly an untrusted proposal. The model cannot supply tenant IDs, user IDs, credentials, or execute arbitrary code.
- **Deterministic Permission Gate:** Every tool execution requires explicit scopes (e.g. `crm.read`, `crm.write`, `slack.send`, `gmail.send`) verified against the caller's authorized permissions.
- **Risk Classification & Elevation Gate:**
  - `LOW`: Executes autonomously based on the chosen mode.
  - `MEDIUM`: Enforces human approval. Execution pauses in an `awaiting_confirmation` state until approved or rejected.
  - `HIGH`: Destructive or unauthorized elevated actions are **blocked outright**.
- **Replay Protection & Confirmation Isolation:** Approved operations execute exactly once; rejected operations execute zero times. Confirmation tokens cannot be replayed or approved across tenants.

### 3. Integration & Credential Manager (`/integrations`)
- Connectors for **Gmail**, **Slack**, and **CRM**.
- **Zero Client Credential Exposure:** Secrets entered into the browser are sent directly to FastAPI, registered in-memory as opaque references (`cred_...`), and securely mapped to n8n credentials server-to-server.
- The browser, LLM, and raw workflow JSON **never receive or render raw API keys or passwords**.

### 4. Interactive Web Application (`frontend/`)
- **Dashboard (`/dashboard`):** Real-time KPI statistics (Total Automations, Active Automations, Integrations, Executions, Recent Errors), gateway health status, quick actions, and recent activity widgets.
- **Agent Console (`/agent`):** Conversational chat interface featuring mode pills (`ASK`, `DO`, `AUTOMATE`), plan step breakdowns, execution result cards, and human-in-the-loop confirmation approvals.
- **Automations Management (`/automations` & `/automations/[id]`):** Searchable automation catalog with status filters and a full visual DAG timeline inspector showing triggers and action steps with sanitized parameters.
- **Integration Management (`/integrations`):** Real-time connector cards, masked credential entry modals with eye toggle, and impact-warning disconnection dialogs.
- **Activity Stream (`/activity`):** Immutable, tamper-evident audit trail (`gnani_audit_events`) with category filters, instant search, and bounded pagination.
- **Executions History (`/executions`):** Observational telemetry table (`gnani_executions`) detailing execution statuses, modes, durations (`formatDuration`), started timestamps, and detail inspection modals.

### 5. Durable PostgreSQL Persistence & Observability
- 8 dedicated PostgreSQL tables:
  1. `gnani_credential_references`: Secure reference mappings.
  2. `gnani_integration_connections`: Tenant connection statuses.
  3. `gnani_automations`: Canonical workflows and n8n workflow mappings.
  4. `gnani_conversations`: Multi-turn chat sessions.
  5. `gnani_conversation_messages`: Chat history with redacted metadata.
  6. `gnani_memory`: Scoped long-term memory.
  7. `gnani_audit_events`: Tamper-evident audit trail.
  8. `gnani_executions`: Operational telemetry logs.
- **Storage-Level Redaction:** Automatic pre-storage scrubbing (`_safe_json` / `_safe_text`) redacts all sensitive credential values to `[REDACTED]`.
- **Fail-Closed Persistence:** The system fails closed with HTTP 503 (`DATABASE_UNAVAILABLE`) if the database is unreachable, with zero silent fallbacks.

### 6. Voice Input via Prisma STT
- Direct microphone capture via `sounddevice` and `scipy.io.wavfile`.
- High-fidelity speech-to-text transcription via the Prisma STT API.
- Spoken requests pipe directly into `Agent.run()`.

---

## Quick Start & Setup Guide

### Prerequisites
- **Python:** 3.11+
- **Node.js:** 18+ (tested on Node 20 & Node 24)
- **Docker Desktop:** Installed and running
- **Operating System:** Windows, macOS, or Linux

---

### Step 1: Environment Configuration

Copy the example environment template and configure your keys:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` in your editor and configure the necessary credentials:
- `GEMINI_API_KEY`: Google Gemini API key for AI reasoning and planning.
- `GNANI_API_KEY`: API key for Prisma STT (or `VOICE2FLOW_API_KEY` - optional if using text-only chat).
- `DATABASE_URL`: Connection string to PostgreSQL (`postgresql://gnani:gnani_secret@localhost:5432/gnani_agent`).
- `N8N_BASE_URL`: Local or remote n8n instance (`http://localhost:5678`).
- `N8N_API_KEY`: n8n API Key (generated inside n8n Settings → n8n API).

*(Note: Never commit your `.env` file to version control.)*

---

### Step 2: Start Infrastructure (Docker)

Start PostgreSQL, n8n, and Redis containers in the background:

```bash
cd docker
docker-compose up -d
cd ..
```

Verify that all services are healthy:
- **PostgreSQL:** Running on `localhost:5432`
- **n8n:** Running on `http://localhost:5678` (Default login: `admin` / `gnani_n8n_secret`)
- **Redis:** Running on `localhost:6379`

To verify n8n health directly:
```bash
curl http://localhost:5678/healthz
# Expected: {"status":"ok"}
```

---

### Step 3: Set Up Python Backend

Create and activate a virtual environment, then install all Python dependencies:

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt
```

---

### Step 4: Set Up Next.js Frontend

Navigate to the `frontend/` directory and install the Node.js packages:

```bash
cd frontend
npm install
cd ..
```

---

### Step 5: Run the Services

#### Option A: Start FastAPI Backend
In your first terminal (with `.venv` activated):
```bash
python -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload
```
- API Base URL: `http://localhost:8000`
- Interactive Swagger Docs: `http://localhost:8000/docs`
- Gateway Liveness: `http://localhost:8000/api/healthz`

#### Option B: Start Next.js Frontend
In your second terminal:
```bash
cd frontend
npm run dev
```
- Open your browser at: **`http://localhost:3000`**

#### Option C: Run Interactive CLI Demo
To run an end-to-end command-line demonstration of tool dispatching and Gemini agent planning:
```bash
python run_demo.py
```

#### Option D: Run Voice Agent (Microphone STT)
To initiate a hands-free microphone voice session using Prisma STT:
```bash
python -m backend.voice.voice_agent
```

---

## API Endpoints Reference

All protected API endpoints require tenant authentication headers:
- `X-Organization-Id`: Tenant organization identifier (e.g. `org_demo_001`).
- `X-User-Id`: Authenticated user identifier (e.g. `user_demo_001`).
- `X-User-Permissions`: Comma-delimited permission scopes (e.g. `crm.read,crm.write,slack.send,gmail.send`).

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/healthz` | System and gateway health check. |
| `POST` | `/api/agent/chat` | Send conversational prompt (`message`, optional `conversation_id`). |
| `POST` | `/api/agent/confirm` | Approve or reject pending action (`run_id`, `conversation_id`, `approved`). |
| `GET` | `/api/automations` | List all canonical automations for the tenant. |
| `GET` | `/api/automations/{id}` | Inspect a single canonical automation and its DAG steps. |
| `GET` | `/api/integrations` | List supported tool connectors and their active connection status. |
| `POST` | `/api/integrations/{key}/connect` | Connect a service (`secret`, optional `account_identifier`). |
| `POST` | `/api/integrations/{key}/disconnect` | Disconnect service and revoke in-memory credentials. |
| `GET` | `/api/dashboard/stats` | Retrieve aggregated dashboard counts (automations, integrations, executions). |
| `GET` | `/api/activity` | Paginated audit event log stream (`limit`, `offset`). |
| `GET` | `/api/executions` | Paginated operational execution telemetry (`limit`, `offset`). |

---

## Testing & Quality Assurance

The codebase includes an extensive, fully automated test suite verifying all 11 phases.

### 1. Run the Full Pytest Regression Suite
```bash
.\.venv\Scripts\pytest.exe tests --tb=short
```
*Current Baseline: **177 passed**, 0 failed, 0 skipped.*

### 2. Verify Python Compilation
```bash
python -m compileall backend tests
```
*Ensures all modules compile cleanly with exit code 0.*

### 3. Run Next.js Production Build
```bash
npm --prefix frontend run build
```
*Validates TypeScript types, React 19 rules, and static route generation across all 10 pages.*

---

## Project Structure

```text
business-agent-dev/
├── backend/
│   ├── agent/                      # Core agent orchestration
│   │   ├── agent.py                # Main Agent class & execution loop
│   │   ├── automation_manager.py   # Canonical automation lifecycle & persistence
│   │   ├── confirmation_manager.py # Risk scoring & human approval evaluation
│   │   ├── context_manager.py      # Conversation state & turn history
│   │   ├── execution_manager.py    # Direct tool execution & dispatcher
│   │   ├── permission_manager.py   # Deterministic scope verification
│   │   ├── planner.py              # Gemini LLM plan synthesizer
│   │   ├── tool_registry.py        # Tool definitions, schemas & risk levels
│   │   ├── validator.py            # Plan & parameter schema validator
│   │   └── workflow_compiler.py    # Canonical AST to n8n workflow compiler
│   ├── api/                        # FastAPI application layer
│   │   ├── app.py                  # ASGI app, CORS & exception handlers
│   │   ├── dependencies.py         # Tenant context & repository injection
│   │   ├── schemas.py              # Pydantic request & response models
│   │   └── routes/                 # Route modules (agent, automations, etc.)
│   ├── integrations/               # Integrations & persistence infrastructure
│   │   ├── connection_manager.py   # IntegrationManager & tenant connections
│   │   ├── credential_manager.py   # Opaque credential reference provider
│   │   ├── n8n_client.py           # n8n REST v1 API client & webhook invoker
│   │   ├── n8n_credentials.py      # n8n credential provisioning & mapping
│   │   ├── persistence.py          # SQLite repository (testing fallback)
│   │   └── postgres_persistence.py # Production PostgreSQL repository
│   ├── voice/                      # Voice & Speech-to-Text
│   │   ├── microphone.py           # Audio capture using sounddevice
│   │   ├── prisma_client.py        # Prisma STT REST client
│   │   └── voice_agent.py          # End-to-end voice session runner
│   └── requirements.txt            # Python dependencies
├── frontend/                       # Next.js 15 Web Application
│   ├── src/
│   │   ├── app/                    # App Router pages
│   │   │   ├── dashboard/          # Operations overview
│   │   │   ├── agent/              # Interactive chat & confirmation console
│   │   │   ├── automations/        # Workflow catalog & DAG inspector
│   │   │   ├── integrations/       # Connector management console
│   │   │   ├── activity/           # Tamper-evident audit timeline
│   │   │   └── executions/         # Execution history & telemetry
│   │   ├── components/             # Reusable modular UI components
│   │   └── lib/                    # API client, React Query hooks & types
│   ├── package.json
│   └── tailwind.config.ts
├── database/                       # SQL schema & seed scripts
├── docker/                         # Docker Compose (PostgreSQL, n8n, Redis)
├── docs/                           # Architectural specifications & audits
├── tests/                          # 177 unit & integration tests
├── .env.example                    # Environment variable template
├── README.md                       # Documentation
└── run_demo.py                     # Interactive CLI demonstration
```

---

## Security & Privacy Highlights

- **Zero Client Credential Storage:** No passwords, access tokens, or API keys are stored in `localStorage`, `sessionStorage`, or cookies.
- **Tenant Isolation:** All database tables enforce `organization_id` filters with parameterized queries (`%s`). Cross-tenant access is rejected at the query level.
- **Storage Redaction:** The regex engine scrubs secret values before database commits, ensuring plain-text secrets never enter database dumps or audit logs.
- **Direct Infrastructure Isolation:** The browser client only connects to port `8000` (FastAPI). It has zero direct access to PostgreSQL (`5432`), n8n (`5678`), or external provider APIs.

---

## License

This project is proprietary and confidential. Developed for the Voice2Flow AI Business Agent Platform.
