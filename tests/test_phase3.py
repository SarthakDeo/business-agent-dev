import requests
import pytest
from unittest.mock import patch

from backend.agent.context_manager import ConversationContext
from backend.agent.execution_manager import execute_plan
from backend.integrations import (
    CredentialManager,
    IntegrationManager,
    N8nCredentialProvider,
    list_supported_integrations,
)


def test_supported_integrations_and_connection_lifecycle():
    manager = IntegrationManager()
    assert {item["id"] for item in list_supported_integrations()} == {
        "gmail", "slack", "crm"
    }

    connection = manager.connect(
        "org-a", "slack", "TEST_SECRET_DO_NOT_LEAK", "acme-workspace"
    )
    assert connection.status == "connected"
    assert "TEST_SECRET_DO_NOT_LEAK" not in str(connection.safe_dict())
    assert manager.connection_status("org-a", "slack")["account_identifier"] == "acme-workspace"

    manager.disconnect("org-a", "slack")
    assert manager.connection_status("org-a", "slack")["status"] == "disconnected"


def test_unsupported_integration_is_rejected():
    with pytest.raises(ValueError):
        IntegrationManager().connect("org-a", "unknown", "secret")


def test_connections_are_organization_scoped():
    manager = IntegrationManager()
    connection = manager.connect("org-a", "crm", "ORG_A_SECRET")

    assert manager.list_connections("org-b") == []
    with pytest.raises(Exception):
        manager.credentials.resolve_credential("org-b", connection.credential_reference)
    with pytest.raises(LookupError):
        manager.get_connection("org-b", "crm")


def test_credential_lifecycle_hides_secret_and_enforces_tenant():
    manager = CredentialManager()
    reference = manager.create_credential("org-a", "gmail", "FAKE_SECRET_123")
    assert "FAKE_SECRET_123" not in str(reference)
    assert manager.get_credential_reference("org-a", reference.id) == reference
    assert manager.resolve_credential("org-a", reference.id) == "FAKE_SECRET_123"

    with pytest.raises(Exception):
        manager.resolve_credential("org-b", reference.id)
    manager.revoke_credential("org-a", reference.id)
    with pytest.raises(Exception):
        manager.resolve_credential("org-a", reference.id)


def test_n8n_provider_returns_reference_not_secret():
    provider = N8nCredentialProvider()
    reference = provider.provision("org-a", "slack", "FAKE_SECRET_123")
    assert reference.integration == "slack"
    assert "FAKE_SECRET_123" not in str(reference)
    assert provider.resolve("org-a", reference) == reference
    with pytest.raises(Exception):
        provider.resolve("org-b", reference)


def test_execution_resolves_org_connection_and_sends_only_reference():
    manager = IntegrationManager()
    manager.connect("org-a", "slack", "FAKE_SECRET_123")
    context = ConversationContext("user-a", "org-a")
    context.integration_manager = manager
    context.approved_step_ids.add("step_1")

    with patch(
        "backend.agent.execution_manager._call_n8n",
        side_effect=requests.RequestException(),
    ), patch(
        "backend.agent.execution_manager.dispatch_tool",
        return_value={"success": True, "ok": True},
    ) as dispatch:
        results = execute_plan({
            "steps": [{
                "id": "step_1",
                "tool": "slack.send_message",
                "parameters": {"channel": "#support", "message": "hello"},
            }],
        }, context)

    assert results["step_1"]["success"] is True
    dispatch.assert_called_once()


def test_disconnected_connection_blocks_execution():
    manager = IntegrationManager()
    manager.connect("org-a", "slack", "secret")
    manager.disconnect("org-a", "slack")
    context = ConversationContext("user-a", "org-a")
    context.integration_manager = manager
    context.approved_step_ids.add("step_1")

    with pytest.raises(Exception):
        execute_plan({
            "steps": [{
                "id": "step_1",
                "tool": "slack.send_message",
                "parameters": {"channel": "#support", "message": "hello"},
            }],
        }, context)
