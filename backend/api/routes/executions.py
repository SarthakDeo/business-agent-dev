"""Execution records routes."""

from typing import Annotated
from fastapi import APIRouter, Depends, Query

from ..dependencies import TenantContext, get_state_store, get_tenant_context
from ..schemas import ExecutionResponse
from ...integrations.postgres_persistence import PostgresStateStore

router = APIRouter(prefix="/api/executions", tags=["Executions"])


@router.get("", response_model=list[ExecutionResponse])
def list_executions(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    store: Annotated[PostgresStateStore, Depends(get_state_store)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ExecutionResponse]:
    """List execution records for the tenant."""
    records = store.list_executions(tenant.organization_id, limit=limit, offset=offset)
    return [
        ExecutionResponse(
            id=r["id"],
            organization_id=r["organization_id"],
            user_id=r.get("user_id"),
            automation_id=r.get("automation_id"),
            request_id=r.get("request_id"),
            mode=r["mode"],
            status=r["status"],
            error_code=r.get("error_code"),
            metadata=r.get("metadata") or {},
            started_at=str(r["started_at"]),
            completed_at=str(r["completed_at"]) if r.get("completed_at") else None,
        )
        for r in records
    ]
