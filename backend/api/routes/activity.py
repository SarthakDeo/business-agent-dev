"""Audit event stream for compliance and activity tracking."""

from typing import Annotated
from fastapi import APIRouter, Depends, Query

from ..dependencies import TenantContext, get_state_store, get_tenant_context
from ..schemas import AuditEventResponse
from ...integrations.postgres_persistence import PostgresStateStore

router = APIRouter(prefix="/api/activity", tags=["Activity"])


@router.get("", response_model=list[AuditEventResponse])
def list_activity(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    store: Annotated[PostgresStateStore, Depends(get_state_store)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditEventResponse]:
    """List sanitized audit events for the tenant."""
    events = store.list_audit_events(tenant.organization_id, limit=limit, offset=offset)
    return [
        AuditEventResponse(
            id=e["id"],
            organization_id=e["organization_id"],
            user_id=e.get("user_id"),
            request_id=e.get("request_id"),
            run_id=e.get("run_id"),
            event_type=e["event_type"],
            mode=e.get("mode"),
            action=e.get("action"),
            status=e.get("status"),
            metadata=e.get("metadata") or {},
            created_at=str(e["created_at"]),
        )
        for e in events
    ]
