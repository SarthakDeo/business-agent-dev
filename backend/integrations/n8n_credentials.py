"""Credential-reference to n8n-credential mapping boundary."""

from dataclasses import dataclass
import json
import os
from typing import Any, Optional
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
        extra_data: Optional[dict] = None,
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

        name = f"voice2flow-{organization_id}-{integration}"

        # Build provider-specific credential type and payload data
        if integration == "gmail":
            cred_type = credential_type or "gmailOAuth2"
            token_dict = {}
            if isinstance(secret, str):
                try:
                    token_dict = json.loads(secret)
                except Exception:
                    token_dict = {"access_token": secret}
            elif isinstance(secret, dict):
                token_dict = secret

            if "oauthTokenData" in token_dict:
                data = dict(token_dict)
            else:
                oauth_token_data = {
                    "access_token": token_dict.get("access_token", secret),
                    "token_type": token_dict.get("token_type", "Bearer"),
                    "scope": token_dict.get(
                        "scope",
                        "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send",
                    ),
                    "expires_in": token_dict.get("expires_in", 3600),
                }
                if "refresh_token" in token_dict and token_dict["refresh_token"]:
                    oauth_token_data["refresh_token"] = token_dict["refresh_token"]
                data = {"oauthTokenData": oauth_token_data}

            client_id = (
                os.environ.get("GOOGLE_CLIENT_ID")
                or os.environ.get("VOICE2FLOW_GOOGLE_CLIENT_ID")
                or os.environ.get("GNANI_GOOGLE_CLIENT_ID")
            )
            client_secret = (
                os.environ.get("GOOGLE_CLIENT_SECRET")
                or os.environ.get("VOICE2FLOW_GOOGLE_CLIENT_SECRET")
                or os.environ.get("GNANI_GOOGLE_CLIENT_SECRET")
            )
            if client_id and "clientId" not in data:
                data["clientId"] = client_id
            if client_secret and "clientSecret" not in data:
                data["clientSecret"] = client_secret

        elif integration == "slack":
            cred_type = credential_type or "slackApi"
            data = {"accessToken": secret, "value": secret}

        elif integration == "crm":
            cred_type = credential_type or "httpHeaderAuth"
            data = {"name": "X-API-Key", "value": secret}

        else:
            cred_type = credential_type or f"voice2flow-{integration}"
            data = {"value": secret}

        if extra_data:
            data.update(extra_data)

        response = client.create_credential(
            cred_type,
            name,
            data,
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

    def delete_mapping(
        self, organization_id: str, credential_reference: str, client: Optional[Any] = None
    ) -> None:
        """Permanently delete an n8n credential and its mapping."""
        ref = self._references.pop(credential_reference, None)
        if ref and client and hasattr(client, "delete_credential"):
            try:
                client.delete_credential(ref.id)
            except Exception:
                pass
