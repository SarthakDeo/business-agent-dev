"""Organization-scoped integration connection management."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import logging
from uuid import uuid4

logger = logging.getLogger(__name__)

from .credential_manager import CredentialManager, CredentialReference
from .n8n_client import N8nClient
from .n8n_credentials import N8nCredentialProvider
from .integration_registry import get_integration, list_supported_integrations
from .persistence import IntegrationStateStore


@dataclass
class IntegrationConnection:
    id: str
    organization_id: str
    integration: str
    status: str
    credential_reference: str
    account_identifier: str | None
    created_at: str
    updated_at: str

    def safe_dict(self) -> dict:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "integration": self.integration,
            "status": self.status,
            "credential_reference": self.credential_reference,
            "account_identifier": self.account_identifier,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class IntegrationManager:
    def __init__(
        self,
        credential_manager: CredentialManager | None = None,
        state_store: IntegrationStateStore | None = None,
        n8n_client: N8nClient | None = None,
        n8n_credential_provider: N8nCredentialProvider | None = None,
    ):
        self._state_store = (
            state_store
            or getattr(credential_manager, "_state_store", None)
            or IntegrationStateStore(":memory:")
        )
        self.credentials = credential_manager or CredentialManager(self._state_store)
        self._connections: dict[tuple[str, str], IntegrationConnection] = {}
        self.n8n_client = n8n_client
        self.n8n_credential_provider = n8n_credential_provider or N8nCredentialProvider()

    def list_supported_integrations(self) -> list[dict]:
        return list_supported_integrations()

    def connect(
        self,
        organization_id: str,
        integration: str,
        secret: str,
        account_identifier: str | None = None,
    ) -> IntegrationConnection:
        get_integration(integration)
        reference = self.credentials.create_credential(
            organization_id, integration, secret
        )

        # --- Auto-provision n8n credential when an n8n client is configured ---
        # If provisioning fails we roll back the Voice2Flow credential so the
        # connection is never stored in a half-ready state.
        if self.n8n_client is not None:
            try:
                n8n_ref = self.n8n_credential_provider.provision(
                    organization_id, integration, secret, client=self.n8n_client
                )
                self.n8n_credential_provider.register_mapping(
                    organization_id, reference.id, n8n_ref.id, integration
                )
            except Exception:
                # Roll back: revoke the Voice2Flow credential and do not store the connection.
                self.credentials.revoke_credential(organization_id, reference.id)
                raise

        now = datetime.now(timezone.utc).isoformat()
        connection = IntegrationConnection(
            id=f"conn_{uuid4().hex}",
            organization_id=organization_id,
            integration=integration,
            status="connected",
            credential_reference=reference.id,
            account_identifier=account_identifier,
            created_at=now,
            updated_at=now,
        )
        self._connections[(organization_id, integration)] = connection
        if self._state_store:
            self._state_store.save_connection(asdict(connection))
        return connection

    def get_connection(
        self, organization_id: str, integration: str
    ) -> IntegrationConnection:
        connection = self._connections.get((organization_id, integration))
        if not connection and self._state_store:
            row = self._state_store.get_connection(organization_id, integration)
            if row:
                connection = IntegrationConnection(**row)
                self._connections[(organization_id, integration)] = connection
        if not connection:
            raise LookupError("Integration is not connected")
        return connection

    def list_connections(self, organization_id: str) -> list[dict]:
        connections = [
            connection.safe_dict()
            for (org_id, _), connection in self._connections.items()
            if org_id == organization_id
        ]
        if self._state_store:
            persisted = self._state_store.list_connections(organization_id)
            known = {(item["organization_id"], item["integration"]) for item in connections}
            connections.extend(
                item for item in persisted
                if (item["organization_id"], item["integration"]) not in known
            )
        return connections

    def connection_status(self, organization_id: str, integration: str) -> dict:
        return self.get_connection(organization_id, integration).safe_dict()

    def disconnect(self, organization_id: str, integration: str) -> None:
        connection = self.get_connection(organization_id, integration)
        cred_ref = connection.credential_reference

        # 1. Clean up n8n credential and mapping
        if hasattr(self, "n8n_credential_provider") and self.n8n_credential_provider:
            try:
                self.n8n_credential_provider.delete_mapping(
                    organization_id, cred_ref, client=getattr(self, "n8n_client", None)
                )
            except Exception as exc:
                logger.warning(f"Error deleting n8n credential for {integration}: {exc}")

        # 2. Delete secret & credential reference completely from CredentialManager
        if cred_ref:
            self.credentials.delete_credential(organization_id, cred_ref)

        # 3. Strip all credential & account data from the connection
        connection.credential_reference = ""
        connection.account_identifier = None
        connection.status = "disconnected"
        connection.updated_at = datetime.now(timezone.utc).isoformat()

        # 4. Delete all credential references from database state store
        if self._state_store:
            if hasattr(self._state_store, "delete_credential_reference") and cred_ref:
                self._state_store.delete_credential_reference(cred_ref)
            self._state_store.save_connection(asdict(connection))

    def resolve_credential_reference(
        self, organization_id: str, integration: str
    ) -> CredentialReference:
        connection = self.get_connection(organization_id, integration)
        if connection.status != "connected":
            raise LookupError("Integration is not connected")
        return self.credentials.get_credential_reference(
            organization_id, connection.credential_reference
        )

    def resolve_integration(
        self, organization_id: str, integration: str
    ) -> CredentialReference:
        """Resolve the connected integration to a tenant-scoped reference."""
        return self.resolve_credential_reference(organization_id, integration)
