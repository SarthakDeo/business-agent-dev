"""Secret storage and credential-reference lifecycle.

The default store is process-local for development and tests. Secrets are never
returned by the public reference methods or serialized into execution payloads.
"""

from dataclasses import dataclass
from uuid import uuid4
from datetime import datetime, timezone

from .persistence import IntegrationStateStore


class CredentialError(Exception):
    """Base error for credential lifecycle failures."""


class CredentialNotFoundError(CredentialError):
    pass


class CredentialAccessDeniedError(CredentialError):
    pass


@dataclass(frozen=True)
class CredentialReference:
    id: str
    organization_id: str
    integration: str
    status: str = "active"


class CredentialManager:
    def __init__(self, state_store: IntegrationStateStore | None = None):
        self._references: dict[str, CredentialReference] = {}
        self._secrets: dict[str, str] = {}
        self._state_store = state_store

    def create_credential(
        self, organization_id: str, integration: str, secret: str
    ) -> CredentialReference:
        if not secret:
            raise CredentialError("Credential secret cannot be empty")
        reference = CredentialReference(
            id=f"cred_{uuid4().hex}",
            organization_id=organization_id,
            integration=integration,
        )
        self._references[reference.id] = reference
        self._secrets[reference.id] = secret
        if self._state_store:
            self._state_store.save_credential_reference(
                reference, datetime.now(timezone.utc).isoformat()
            )
        return reference

    def get_credential_reference(
        self, organization_id: str, credential_id: str
    ) -> CredentialReference:
        reference = self._references.get(credential_id)
        if not reference and self._state_store:
            row = self._state_store.get_credential_reference(credential_id)
            if row:
                reference = CredentialReference(**row)
                self._references[credential_id] = reference
        if not reference:
            raise CredentialNotFoundError("Credential reference not found")
        if reference.organization_id != organization_id:
            raise CredentialAccessDeniedError("Credential belongs to another organization")
        return reference

    def resolve_credential(self, organization_id: str, credential_id: str) -> str:
        reference = self.get_credential_reference(organization_id, credential_id)
        if reference.status != "active":
            raise CredentialError("Credential is not active")
        return self._secrets[reference.id]

    def revoke_credential(self, organization_id: str, credential_id: str) -> None:
        reference = self.get_credential_reference(organization_id, credential_id)
        self._references[credential_id] = CredentialReference(
            id=reference.id,
            organization_id=reference.organization_id,
            integration=reference.integration,
            status="revoked",
        )
        self._secrets.pop(credential_id, None)
        if self._state_store:
            self._state_store.save_credential_reference(
                self._references[credential_id], datetime.now(timezone.utc).isoformat()
            )

    def delete_credential(self, organization_id: str, credential_id: str) -> None:
        self.get_credential_reference(organization_id, credential_id)
        self._references.pop(credential_id, None)
        self._secrets.pop(credential_id, None)
