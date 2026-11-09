"""Integration management routes."""

import json
import logging
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from ..dependencies import TenantContext, get_integration_manager, get_tenant_context
from ..schemas import (
    IntegrationConnectRequest,
    IntegrationConnectResponse,
    IntegrationDisconnectResponse,
    IntegrationStatusResponse,
    OAuthCallbackRequest,
    OAuthUrlResponse,
)
from ...integrations.connection_manager import IntegrationManager
from ...integrations.oauth_service import (
    exchange_google_code,
    fetch_google_user_email,
    get_google_auth_url,
    is_google_oauth_configured,
    verify_and_consume_oauth_state,
)

logger = logging.getLogger(__name__)

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
        is_conn = conn and conn.get("status") == "connected"
        results.append(
            IntegrationStatusResponse(
                integration=key,
                name=item.get("name", key.upper()),
                status=conn["status"] if conn else "disconnected",
                account_identifier=conn.get("account_identifier") if is_conn else None,
                connected_at=str(conn.get("created_at")) if is_conn and conn.get("created_at") else None,
                auth_type=item.get("auth_type"),
                description=item.get("description"),
            )
        )
    return results


# ─── GMAIL OAUTH ENDPOINTS ────────────────────────────────────────────────────

@router.get("/gmail/oauth/url", response_model=OAuthUrlResponse)
def get_gmail_oauth_url_endpoint(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    redirect_uri: Optional[str] = None,
) -> OAuthUrlResponse:
    """Generate a CSRF-protected Google OAuth 2.0 authorization URL for Gmail."""
    if not is_google_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in the server environment.",
        )
    try:
        auth_url, state = get_google_auth_url(
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            redirect_uri=redirect_uri,
        )
        return OAuthUrlResponse(url=auth_url, state=state, configured=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate Google OAuth URL: {exc}",
        ) from exc


@router.post("/gmail/oauth/callback", response_model=IntegrationConnectResponse)
def handle_gmail_oauth_callback(
    request: OAuthCallbackRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> IntegrationConnectResponse:
    """Exchange authorization code for Gmail OAuth tokens and provision credential."""
    state_info = verify_and_consume_oauth_state(
        state=request.state,
        organization_id=tenant.organization_id,
    )
    if not state_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state parameter.",
        )
    try:
        tokens = exchange_google_code(
            code=request.code,
            redirect_uri=request.redirect_uri or state_info.get("redirect_uri"),
        )
        user_email = fetch_google_user_email(tokens.get("access_token", ""))
        account_id = user_email or f"gmail-{tenant.organization_id}"

        conn = manager.connect(
            organization_id=tenant.organization_id,
            integration="gmail",
            secret=json.dumps(tokens),
            account_identifier=account_id,
        )
        return IntegrationConnectResponse(
            status=conn.status,
            integration="gmail",
            account_identifier=conn.account_identifier,
        )
    except Exception as exc:
        logger.error(f"Failed to complete Gmail OAuth connection: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gmail OAuth connection failed: {exc}",
        ) from exc


@router.get("/gmail/oauth/callback", response_class=HTMLResponse)
def handle_gmail_oauth_browser_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)] = None,
):
    """Browser redirect callback for Google OAuth popup or redirect flow."""
    if error:
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;background:#0f172a;color:#f87171;padding:2rem;text-align:center;'>"
            f"<h3>Google Authorization Failed</h3><p>{error}</p>"
            f"<script>if(window.opener)window.opener.postMessage({{type:'OAUTH_ERROR',error:'{error}'}},'*');</script>"
            f"</body></html>",
            status_code=400,
        )
    if not code or not state:
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;background:#0f172a;color:#f87171;padding:2rem;text-align:center;'>"
            "<h3>Missing code or state parameter</h3></body></html>",
            status_code=400,
        )

    state_info = verify_and_consume_oauth_state(state=state)
    if not state_info:
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;background:#0f172a;color:#f87171;padding:2rem;text-align:center;'>"
            "<h3>Invalid or expired OAuth state</h3></body></html>",
            status_code=400,
        )

    org_id = state_info.get("organization_id", "default")
    try:
        tokens = exchange_google_code(code=code, redirect_uri=state_info.get("redirect_uri"))
        user_email = fetch_google_user_email(tokens.get("access_token", ""))
        account_id = user_email or f"gmail-{org_id}"

        manager.connect(
            organization_id=org_id,
            integration="gmail",
            secret=json.dumps(tokens),
            account_identifier=account_id,
        )
        return HTMLResponse(
            f"""<!DOCTYPE html>
<html>
<head><title>Gmail Connected - Voice2Flow</title></head>
<body style="font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; background: #0f172a; color: white; margin: 0;">
  <div style="text-align: center; background: #1e293b; padding: 2.5rem; border-radius: 1rem; border: 1px solid #334155; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);">
    <h2 style="color: #38bdf8; margin-top: 0;">Gmail Connected!</h2>
    <p style="color: #94a3b8; font-size: 0.95rem;">Connected as <strong>{account_id}</strong></p>
    <p style="color: #64748b; font-size: 0.85rem;">Closing window and returning to Voice2Flow...</p>
    <script>
      if (window.opener) {{
        window.opener.postMessage({{ type: 'OAUTH_COMPLETE', integration: 'gmail', status: 'connected', account_identifier: '{account_id}' }}, '*');
        setTimeout(() => window.close(), 1200);
      }} else {{
        setTimeout(() => {{ window.location.href = '/integrations?connected=gmail'; }}, 1200);
      }}
    </script>
  </div>
</body>
</html>"""
        )
    except Exception as exc:
        logger.error(f"OAuth browser callback failure: {exc}")
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;background:#0f172a;color:#f87171;padding:2rem;text-align:center;'>"
            f"<h3>Connection Failed</h3><p>{exc}</p></body></html>",
            status_code=400,
        )


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
