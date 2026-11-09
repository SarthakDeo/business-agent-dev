"""Credential-reference to n8n-credential mapping boundary."""

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from .n8n_client import N8nClient


class N8nCredentialError(Exception):
    pass


@dataclass(frozen=True)
class N8nCredentialReference:
    id: str
    organization_id: str
    integration: str


class N8nCredentialProvider:
    def __init__(self):
        self._references: dict[str, N8nCredentialReference] = {}

    def provision(
        self,
        organization_id: str,
        integration: str,
        secret: str,
        client: Optional[N8nClient] = None,
        credential_type: Optional[str] = None,
    ):
        if not secret:
            raise N8nCredentialError("Credential cannot be empty")
        if client is None:
            # Phase 3 compatibility: this is only a local reference, not an
            # n8n credential ID and cannot be used for n8n execution.
            return N8nCredentialReference(
                id=f"ref_{uuid4().hex}",
                organization_id=organization_id,
                integration=integration,
            )
        response = client.create_credential(
            credential_type or f"gnani-{integration}",
            f"gnani-{organization_id}-{integration}",
            {"value": secret},
        )
        reference = N8nCredentialReference(
            id=str(response["id"]),
            organization_id=organization_id,
            integration=integration,
        )
        self._references[reference.id] = reference
        return reference

    def resolve(self, organization_id: str, reference: N8nCredentialReference):
        if reference.organization_id != organization_id:
            raise N8nCredentialError("Credential belongs to another organization")
        return reference

    def register_mapping(
        self, organization_id: str, credential_reference: str, n8n_credential_id: str, integration: str
    ) -> N8nCredentialReference:
        if not n8n_credential_id:
            raise N8nCredentialError("n8n credential ID is required")
        reference = N8nCredentialReference(
            id=n8n_credential_id,
            organization_id=organization_id,
            integration=integration,
        )
        self._references[credential_reference] = reference
        return reference

    def resolve_reference(self, organization_id: str, credential_reference: str) -> N8nCredentialReference:
        reference = self._references.get(credential_reference)
        if reference is None:
            raise N8nCredentialError("Credential reference is not mapped to n8n")
        return self.resolve(organization_id, reference)

    def revoke(self, organization_id: str, reference: N8nCredentialReference):
        self.resolve(organization_id, reference)
