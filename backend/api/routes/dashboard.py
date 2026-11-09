"""Dashboard overview metrics and statistics."""

from typing import Annotated
from fastapi import APIRouter, Depends

from ..dependencies import TenantContext, get_state_store, get_tenant_context
from ..schemas import DashboardStatsResponse
from ...integrations.postgres_persistence import PostgresStateStore

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
def get_stats(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    store: Annotated[PostgresStateStore, Depends(get_state_store)],
) -> DashboardStatsResponse:
    """Retrieve high-level overview metrics scoped to the current tenant."""
    stats = store.get_dashboard_stats(tenant.organization_id)
    return DashboardStatsResponse(**stats)
