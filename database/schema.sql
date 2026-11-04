-- ============================================================
-- GNANI AI BUSINESS AGENT — PostgreSQL Schema
-- Run order: this file is auto-loaded by Docker on first start
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─────────────────────────────────────────
-- 1. ORGANIZATIONS (tenant boundary)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organizations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    slug          TEXT UNIQUE NOT NULL,
    is_demo       BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- 2. USERS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           TEXT UNIQUE NOT NULL,
    full_name       TEXT,
    role            TEXT NOT NULL DEFAULT 'member',  -- admin | member | viewer
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- 3. PERMISSIONS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS permissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    scope           TEXT NOT NULL,  -- crm.read | gmail.send | slack.send | admin | etc.
    granted_at      TIMESTAMPTZ DEFAULT NOW(),
    granted_by      UUID REFERENCES users(id),
    UNIQUE(user_id, scope)
);

-- ─────────────────────────────────────────
-- 4. INTEGRATIONS (connected external services)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS integrations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    service         TEXT NOT NULL,  -- gmail | slack | crm | whatsapp | calendar
    display_name    TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    config_json     JSONB DEFAULT '{}',
    connected_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- 5. CREDENTIALS (metadata only — no raw secrets)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS credentials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_id  UUID NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
    credential_type TEXT NOT NULL,  -- oauth2 | api_key | service_account
    secret_ref      TEXT NOT NULL,  -- reference to secret store (e.g. env var name or vault path)
    is_valid        BOOLEAN DEFAULT TRUE,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- 6. TOOLS (registered tool catalog)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tools (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT UNIQUE NOT NULL,  -- e.g. crm.create_ticket
    description     TEXT,
    integration     TEXT NOT NULL,
    risk_level      TEXT NOT NULL DEFAULT 'low',   -- low | medium | high
    required_permission TEXT NOT NULL,
    input_schema    JSONB NOT NULL DEFAULT '{}',
    output_schema   JSONB NOT NULL DEFAULT '{}',
    n8n_workflow_id TEXT,  -- n8n workflow to call
    is_active       BOOLEAN DEFAULT TRUE,
    version         TEXT DEFAULT '1.0.0',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- 7. CONVERSATIONS (chat sessions)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    title           TEXT,
    status          TEXT DEFAULT 'active',  -- active | archived
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- 8. MESSAGES (individual messages in a conversation)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,  -- user | agent | system
    content         TEXT NOT NULL,
    content_type    TEXT DEFAULT 'text',  -- text | voice
    audio_url       TEXT,  -- if voice input, URL to audio
    transcript      TEXT,  -- Prisma transcript
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- 9. AGENT RUNS (each planning + execution run)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    message_id      UUID REFERENCES messages(id),
    mode            TEXT NOT NULL,  -- ASK | DO | AUTOMATE
    goal            TEXT,           -- the user's stated goal
    evon_plan       JSONB,          -- raw structured plan from Evon
    status          TEXT DEFAULT 'pending',  -- pending | running | awaiting_approval | completed | failed
    error_message   TEXT,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER
);

-- ─────────────────────────────────────────
-- 10. TOOL CALLS (individual tool invocations within a run)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tool_calls (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_run_id    UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    tool_name       TEXT NOT NULL,
    step_id         TEXT,           -- e.g. step_1 from Evon plan
    input_params    JSONB NOT NULL DEFAULT '{}',
    validated_params JSONB,
    output_result   JSONB,
    n8n_execution_id TEXT,
    status          TEXT DEFAULT 'pending',  -- pending | running | completed | failed | blocked
    risk_level      TEXT,
    requires_confirmation BOOLEAN DEFAULT FALSE,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER,
    error_code      TEXT,
    error_message   TEXT
);

-- ─────────────────────────────────────────
-- 11. APPROVALS (user confirmation required before execution)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS approvals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_run_id    UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    tool_call_id    UUID REFERENCES tool_calls(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    description     TEXT NOT NULL,  -- human-readable description of what needs approval
    status          TEXT DEFAULT 'pending',  -- pending | approved | rejected
    reviewed_by     UUID REFERENCES users(id),
    reviewed_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- 12. AUTOMATIONS (persistent AUTOMATE mode definitions)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS automations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by      UUID NOT NULL REFERENCES users(id),
    name            TEXT NOT NULL,
    description     TEXT,
    trigger_type    TEXT NOT NULL,  -- schedule | event | webhook
    trigger_config  JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN DEFAULT TRUE,
    n8n_workflow_id TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- 13. AUTOMATION STEPS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS automation_steps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    automation_id   UUID NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    step_order      INTEGER NOT NULL,
    tool_name       TEXT NOT NULL,
    parameters      JSONB NOT NULL DEFAULT '{}',
    depends_on      TEXT,  -- step ID dependency
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- 14. WORKFLOW EXECUTIONS (runtime instances of automations)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workflow_executions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    automation_id   UUID REFERENCES automations(id),
    agent_run_id    UUID REFERENCES agent_runs(id),
    n8n_execution_id TEXT,
    status          TEXT DEFAULT 'running',  -- running | completed | failed
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    error_message   TEXT
);

-- ─────────────────────────────────────────
-- 15. EXECUTION LOGS (detailed step-by-step events)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS execution_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_execution_id UUID REFERENCES workflow_executions(id),
    agent_run_id    UUID REFERENCES agent_runs(id),
    tool_call_id    UUID REFERENCES tool_calls(id),
    log_level       TEXT DEFAULT 'info',  -- info | warn | error | debug
    message         TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- 16. AUDIT LOGS (security and compliance)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    user_id         UUID REFERENCES users(id),
    agent_run_id    UUID REFERENCES agent_runs(id),
    tool_call_id    UUID REFERENCES tool_calls(id),
    action          TEXT NOT NULL,  -- tool_call_blocked | approval_requested | approval_granted | etc.
    resource_type   TEXT,
    resource_id     TEXT,
    details         JSONB DEFAULT '{}',
    ip_address      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- INDEXES for performance
-- ─────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_conversation ON agent_runs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_user ON agent_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(agent_run_id);
CREATE INDEX IF NOT EXISTS idx_approvals_run ON approvals(agent_run_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_org ON audit_logs(organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);

-- Also create a separate database for n8n
CREATE DATABASE gnani_n8n;
GRANT ALL PRIVILEGES ON DATABASE gnani_n8n TO gnani;

