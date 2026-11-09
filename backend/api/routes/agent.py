"""Agent interaction routes for chat and confirmation handling."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import (
    TenantContext,
    get_agent,
    get_integration_manager,
    get_or_create_conversation_context,
    get_active_conversation_context,
    get_tenant_context,
)
from ..schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AgentConfirmRequest,
    AgentConfirmResponse,
    PendingConfirmationInfo,
)
from ...agent.agent import Agent
from ...integrations.connection_manager import IntegrationManager

router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post("/chat", response_model=AgentChatResponse)
def chat(
    request: AgentChatRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    agent: Annotated[Agent, Depends(get_agent)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> AgentChatResponse:
    """Submit user message to Agent for ASK, DO, or AUTOMATE processing."""
    conv_id, context = get_or_create_conversation_context(tenant, request.conversation_id, manager)

    agent_response = agent.run(
        user_message=request.message,
        context=context,
        user_permissions=tenant.permissions,
        dry_run=request.dry_run,
    )

    pending_info = None
    if agent_response.status == "awaiting_confirmation":
        pending_info = PendingConfirmationInfo(
            summary=agent_response.response_text,
            risk="medium",
            steps=agent_response.pending_confirmations,
            mode=agent_response.mode,
        )

    return AgentChatResponse(
        response=agent_response.response_text,
        mode=agent_response.mode,
        status=agent_response.status,
        run_id=agent_response.run_id,
        conversation_id=conv_id,
        plan=agent_response.plan,
        pending_confirmation=pending_info,
        execution_results=agent_response.execution_results,
        error=agent_response.error,
        error_code=agent_response.error_code,
    )


@router.post("/confirm", response_model=AgentConfirmResponse)
def confirm(
    request: AgentConfirmRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    agent: Annotated[Agent, Depends(get_agent)],
) -> AgentConfirmResponse:
    """Approve or reject a pending action awaiting confirmation."""
    context = get_active_conversation_context(tenant, request.conversation_id)
    if not context or not getattr(context, "pending_steps", []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending operation found awaiting confirmation for this conversation.",
        )

    if context.run_id and context.run_id != request.run_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Confirmation run_id does not match the pending operation.",
        )

    result = agent.resume_confirmation(context, approved=request.approved, dry_run=request.dry_run)

    return AgentConfirmResponse(
        response=result.response_text,
        status=result.status,
        run_id=result.run_id,
        conversation_id=request.conversation_id,
        execution_results=result.execution_results,
        error=result.error,
        error_code=result.error_code,
    )
