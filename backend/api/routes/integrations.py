"""Integration management routes."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import TenantContext, get_integration_manager, get_tenant_context
from ..schemas import (
    IntegrationConnectRequest,
    IntegrationConnectResponse,
    IntegrationDisconnectResponse,
    IntegrationStatusResponse,
)
from ...integrations.connection_manager import IntegrationManager

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])


@router.get("", response_model=list[IntegrationStatusResponse])
def list_integrations(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> list[IntegrationStatusResponse]:
    """List supported integrations with their active connection status for the tenant."""
    supported = manager.list_supported_integrations()
    connections = {c["integration"]: c for c in manager.list_connections(tenant.organization_id)}

    results = []
    for item in supported:
        key = item["id"]
        conn = connections.get(key)
        results.append(
            IntegrationStatusResponse(
                integration=key,
                name=item.get("name", key.upper()),
                status=conn["status"] if conn else "disconnected",
                account_identifier=conn.get("account_identifier") if conn else None,
                connected_at=str(conn.get("created_at")) if conn else None,
            )
        )
    return results


@router.post("/{integration}/connect", response_model=IntegrationConnectResponse)
def connect_integration(
    integration: str,
    request: IntegrationConnectRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> IntegrationConnectResponse:
    """Connect an integration with credential secret. Raw secrets are never logged or returned."""
    try:
        conn = manager.connect(
            organization_id=tenant.organization_id,
            integration=integration,
            secret=request.secret,
            account_identifier=request.account_identifier,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect integration '{integration}': {exc}",
        ) from exc

    return IntegrationConnectResponse(
        status=conn.status,
        integration=integration,
        account_identifier=conn.account_identifier,
    )


@router.post("/{integration}/disconnect", response_model=IntegrationDisconnectResponse)
def disconnect_integration(
    integration: str,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> IntegrationDisconnectResponse:
    """Disconnect and revoke credentials for an integration."""
    try:
        manager.disconnect(tenant.organization_id, integration)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration '{integration}' is not currently connected.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to disconnect integration '{integration}': {exc}",
        ) from exc

    return IntegrationDisconnectResponse(
        status="disconnected",
        integration=integration,
    )
