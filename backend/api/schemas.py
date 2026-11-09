"""Pydantic schemas for Voice2Flow FastAPI layer."""

from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── AGENT SCHEMAS ────────────────────────────────────────────────────────────

class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User natural language instruction")
    conversation_id: Optional[str] = Field(None, description="Optional existing conversation ID")
    dry_run: bool = Field(False, description="Dry run mode for testing without external side effects")


class PendingConfirmationInfo(BaseModel):
    summary: str
    risk: str = "medium"
    steps: list[dict[str, Any]] = Field(default_factory=list)
    mode: Optional[str] = None


class AgentChatResponse(BaseModel):
    response: str
    mode: str
    status: str
    run_id: str
    conversation_id: str
    plan: dict[str, Any] = Field(default_factory=dict)
    pending_confirmation: Optional[PendingConfirmationInfo] = None
    execution_results: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    error_code: Optional[str] = None


class AgentConfirmRequest(BaseModel):
    run_id: str = Field(..., min_length=1, description="The correlation run_id being confirmed")
    conversation_id: str = Field(..., min_length=1, description="The active conversation ID")
    approved: bool = Field(..., description="True to approve execution, False to cancel")
    dry_run: bool = Field(False, description="Dry run mode for testing")


class AgentConfirmResponse(BaseModel):
    response: str
    status: str
    run_id: str
    conversation_id: str
    execution_results: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    error_code: Optional[str] = None


# ─── AUTOMATION SCHEMAS ───────────────────────────────────────────────────────

class AutomationSummaryResponse(BaseModel):
    id: str
    name: str
    status: str
    n8n_workflow_id: str
    step_count: int
    created_at: str
    updated_at: str


class AutomationDetailResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    status: str
    n8n_workflow_id: str
    canonical_workflow: dict[str, Any]
    created_at: str
    updated_at: str


# ─── INTEGRATION SCHEMAS ──────────────────────────────────────────────────────

class IntegrationStatusResponse(BaseModel):
    integration: str
    name: str
    status: str
    account_identifier: Optional[str] = None
    connected_at: Optional[str] = None


class IntegrationConnectRequest(BaseModel):
    secret: str = Field(..., min_length=1, description="Raw credential secret (never logged or persisted in plain text)")
    account_identifier: Optional[str] = Field(None, description="Optional label or account email")


class IntegrationConnectResponse(BaseModel):
    status: str
    integration: str
    account_identifier: Optional[str] = None


class IntegrationDisconnectResponse(BaseModel):
    status: str
    integration: str


# ─── OBSERVABILITY & STATS SCHEMAS ────────────────────────────────────────────

class DashboardStatsResponse(BaseModel):
    automations: int
    active_automations: int
    integrations: int
    recent_executions: int
    recent_errors: int


class AuditEventResponse(BaseModel):
    id: str
    organization_id: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    run_id: Optional[str] = None
    event_type: str
    mode: Optional[str] = None
    action: Optional[str] = None
    status: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ExecutionResponse(BaseModel):
    id: str
    organization_id: str
    user_id: Optional[str] = None
    automation_id: Optional[str] = None
    request_id: Optional[str] = None
    mode: str
    status: str
    error_code: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: str
    completed_at: Optional[str] = None


# ─── ERROR SCHEMA ─────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    error_code: str
    status: str = "error"
    request_id: Optional[str] = None
