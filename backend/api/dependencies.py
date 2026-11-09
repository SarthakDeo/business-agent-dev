"""Dependency injection and tenant context extraction for FastAPI."""

from dataclasses import dataclass, field
import os
from typing import Annotated, Optional
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, status

from ..agent.agent import Agent
from ..agent.context_manager import ConversationContext
from ..integrations.connection_manager import IntegrationManager
from ..integrations.n8n_client import N8nClient, N8nConfig
from ..integrations.n8n_credentials import N8nCredentialProvider
from ..integrations.postgres_persistence import PostgresPersistenceError, PostgresStateStore


# Development default PostgreSQL DSN; can be overridden via environment variable POSTGRES_DSN
DEFAULT_POSTGRES_DSN = os.environ.get(
    "POSTGRES_DSN",
    "postgresql://gnani_test:gnani_test_password@localhost:5432/gnani_test",
)


@dataclass(frozen=True)
class TenantContext:
    organization_id: str
    user_id: str
    permissions: list[str] = field(default_factory=list)


def get_tenant_context(
    x_organization_id: Annotated[Optional[str], Header()] = None,
    x_user_id: Annotated[Optional[str], Header()] = None,
    x_user_permissions: Annotated[Optional[str], Header()] = None,
) -> TenantContext:
    """
    Extracts development tenant and user context from incoming request headers.
    
    NOTE: These headers are development-only tenant/user context for Phase 11 MVP
    and must not be considered production authentication.
    """
    if not x_organization_id or not x_organization_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required header 'X-Organization-Id'",
        )
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required header 'X-User-Id'",
        )

    perms: list[str] = []
    if x_user_permissions:
        perms = [p.strip() for p in x_user_permissions.split(",") if p.strip()]

    return TenantContext(
        organization_id=x_organization_id.strip(),
        user_id=x_user_id.strip(),
        permissions=perms,
    )


# Global singleton store instance for FastAPI runtime
_global_state_store: Optional[PostgresStateStore] = None
_global_n8n_client: Optional[N8nClient] = None
_n8n_client_set: bool = False
_global_credential_provider: N8nCredentialProvider = N8nCredentialProvider()


def get_state_store() -> PostgresStateStore:
    """
    Returns the PostgreSQL persistence store.
    Fails closed if the database is unreachable, with zero silent fallback to SQLite.
    """
    global _global_state_store
    if _global_state_store is None:
        try:
            _global_state_store = PostgresStateStore(DEFAULT_POSTGRES_DSN)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PostgreSQL persistence backend is unavailable",
            ) from exc
    return _global_state_store


def set_state_store(store: PostgresStateStore | None) -> None:
    """Allows test fixtures to inject custom or test stores."""
    global _global_state_store
    _global_state_store = store


def get_n8n_client() -> Optional[N8nClient]:
    """
    Returns the configured n8n client, or None if base_url is not configured.
    Can be overridden via set_n8n_client().
    """
    global _global_n8n_client, _n8n_client_set
    if _n8n_client_set:
        return _global_n8n_client

    base_url = os.environ.get("N8N_BASE_URL", "http://localhost:5678").strip()
    api_key = os.environ.get("N8N_API_KEY", "").strip()
    if base_url:
        try:
            return N8nClient(N8nConfig(base_url=base_url, api_key=api_key))
        except Exception:
            return None
    return None


def set_n8n_client(client: Optional[N8nClient]) -> None:
    """Allows test fixtures to inject custom or mock n8n clients."""
    global _global_n8n_client, _n8n_client_set
    _global_n8n_client = client
    _n8n_client_set = True


def reset_n8n_client() -> None:
    """Resets the n8n client to re-evaluate from environment on next access."""
    global _global_n8n_client, _n8n_client_set
    _global_n8n_client = None
    _n8n_client_set = False


def get_integration_manager(
    store: Annotated[PostgresStateStore, Depends(get_state_store)],
    n8n_client: Annotated[Optional[N8nClient], Depends(get_n8n_client)] = None,
) -> IntegrationManager:
    return IntegrationManager(
        state_store=store,
        n8n_client=n8n_client,
        n8n_credential_provider=_global_credential_provider,
    )


def get_agent(
    integration_manager: Annotated[IntegrationManager, Depends(get_integration_manager)]
) -> Agent:
    return Agent(integration_manager=integration_manager)


# Scoped in-memory conversation context registry for HTTP session bridging:
# Key: (organization_id, user_id, conversation_id) -> ConversationContext
_session_contexts: dict[tuple[str, str, str], ConversationContext] = {}


def get_or_create_conversation_context(
    tenant: TenantContext,
    conversation_id: Optional[str],
    integration_manager: IntegrationManager,
) -> tuple[str, ConversationContext]:
    """
    Retrieves or establishes a tenant- and user-isolated ConversationContext.
    Guarantees cross-tenant and cross-user isolation.
    """
    conv_id = (conversation_id or "").strip()
    if not conv_id:
        conv_id = f"conv_{uuid4().hex}"

    key = (tenant.organization_id, tenant.user_id, conv_id)
    if key not in _session_contexts:
        ctx = ConversationContext(
            user_id=tenant.user_id,
            org_id=tenant.organization_id,
            conversation_id=conv_id,
            integration_manager=integration_manager,
        )
        _session_contexts[key] = ctx
    else:
        ctx = _session_contexts[key]
        ctx.integration_manager = integration_manager

    return conv_id, ctx


def get_active_conversation_context(
    tenant: TenantContext,
    conversation_id: str,
) -> Optional[ConversationContext]:
    """
    Looks up an existing conversation context for the specified tenant and user.
    Returns None if not found or if attempting cross-tenant access.
    """
    key = (tenant.organization_id, tenant.user_id, conversation_id.strip())
    return _session_contexts.get(key)


def clear_session_contexts() -> None:
    """Utility for testing teardown."""
    _session_contexts.clear()


def clear_credential_mappings() -> None:
    """Utility for testing teardown."""
    _global_credential_provider._references.clear()
