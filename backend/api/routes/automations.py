"""Automation management routes for listing and inspecting canonical workflows."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import TenantContext, get_state_store, get_tenant_context
from ..schemas import AutomationDetailResponse, AutomationSummaryResponse
from ...integrations.postgres_persistence import PostgresStateStore

router = APIRouter(prefix="/api/automations", tags=["Automations"])


@router.get("", response_model=list[AutomationSummaryResponse])
def list_automations(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    store: Annotated[PostgresStateStore, Depends(get_state_store)],
) -> list[AutomationSummaryResponse]:
    """List all automations belonging to the tenant."""
    records = store.list_automations(tenant.organization_id)
    results = []
    for r in records:
        canonical = r.get("canonical_workflow") or {}
        step_count = len(canonical.get("steps", [])) if isinstance(canonical, dict) else 0
        results.append(
            AutomationSummaryResponse(
                id=r["id"],
                name=r["name"],
                status=r["status"],
                n8n_workflow_id=r["n8n_workflow_id"],
                step_count=step_count,
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"]),
            )
        )
    return results


@router.get("/{automation_id}", response_model=AutomationDetailResponse)
def get_automation(
    automation_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    store: Annotated[PostgresStateStore, Depends(get_state_store)],
) -> AutomationDetailResponse:
    """Retrieve full canonical workflow details for a single automation."""
    record = store.get_automation(tenant.organization_id, automation_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Automation '{automation_id}' not found.",
        )

    return AutomationDetailResponse(
        id=record["id"],
        organization_id=record["organization_id"],
        name=record["name"],
        status=record["status"],
        n8n_workflow_id=record["n8n_workflow_id"],
        canonical_workflow=record.get("canonical_workflow") or {},
        created_at=str(record["created_at"]),
        updated_at=str(record["updated_at"]),
    )
