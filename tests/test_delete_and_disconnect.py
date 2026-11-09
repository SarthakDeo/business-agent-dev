"""Tests for deleting automations and wiping all integration data on disconnect."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.dependencies import (
    clear_credential_mappings,
    clear_session_contexts,
    reset_n8n_client,
    set_n8n_client,
    set_state_store,
)
from backend.integrations.connection_manager import IntegrationManager
from backend.integrations.persistence import IntegrationStateStore
from backend.agent.automation_manager import AutomationManager, AutomationNotFoundError


@pytest.fixture
def test_store(tmp_path):
    store = IntegrationStateStore(tmp_path / "test_state.sqlite3")
    set_state_store(store)
    set_n8n_client(None)
    clear_session_contexts()
    clear_credential_mappings()
    yield store
    clear_session_contexts()
    clear_credential_mappings()
    set_state_store(None)
    reset_n8n_client()


@pytest.fixture
def client(test_store):
    return TestClient(app)


# ==============================================================================
# 1. Automation Deletion Tests (StateStore & AutomationManager)
# ==============================================================================

def test_statestore_delete_automation(tmp_path):
    store = IntegrationStateStore(tmp_path / "auto.sqlite3")
    auto_data = {
        "id": "auto_del_1",
        "organization_id": "org_del",
        "n8n_workflow_id": "wf_123",
        "name": "Test Automation to Delete",
        "status": "created",
        "canonical_workflow": {"mode": "AUTOMATE", "steps": []},
    }
    store.save_automation(auto_data)
    assert store.get_automation("org_del", "auto_del_1") is not None

    deleted = store.delete_automation("org_del", "auto_del_1")
    assert deleted is True
    assert store.get_automation("org_del", "auto_del_1") is None

    # Deleting again returns False
    assert store.delete_automation("org_del", "auto_del_1") is False


def test_automation_manager_delete_removes_from_system_and_n8n(tmp_path):
    store = IntegrationStateStore(tmp_path / "auto_mgr.sqlite3")
    mock_n8n = MagicMock()
    mock_n8n.delete_workflow.return_value = {"success": True}

    auto_data = {
        "id": "auto_mgr_del",
        "organization_id": "org_mgr",
        "n8n_workflow_id": "n8n_wf_999",
        "name": "Workflow To Delete",
        "status": "created",
        "canonical_workflow": {"mode": "AUTOMATE", "steps": []},
    }
    store.save_automation(auto_data)

    manager = AutomationManager(state_store=store, n8n_client=mock_n8n)
    res = manager.delete_automation("org_mgr", "auto_mgr_del")

    assert res["status"] == "deleted"
    assert res["automation_id"] == "auto_mgr_del"
    mock_n8n.delete_workflow.assert_called_once_with("n8n_wf_999")
    assert store.get_automation("org_mgr", "auto_mgr_del") is None


def test_automation_manager_delete_nonexistent_raises_not_found(tmp_path):
    store = IntegrationStateStore(tmp_path / "auto_mgr2.sqlite3")
    manager = AutomationManager(state_store=store)
    with pytest.raises(AutomationNotFoundError):
        manager.delete_automation("org_mgr", "nonexistent_auto")


# ==============================================================================
# 2. Automation Deletion API Endpoints
# ==============================================================================

def test_api_delete_automation_endpoint(client, test_store):
    headers = {
        "X-Organization-Id": "org-api-del",
        "X-User-Id": "user-del",
    }

    # Save an automation directly in the store
    test_store.save_automation({
        "id": "auto_api_1",
        "organization_id": "org-api-del",
        "n8n_workflow_id": "wf_n8n_1",
        "name": "API Delete Test",
        "status": "created",
        "canonical_workflow": {
            "mode": "AUTOMATE",
            "trigger": {"type": "webhook", "parameters": {}},
            "steps": [],
        },
    })

    # Verify it exists
    get_res = client.get("/api/automations/auto_api_1", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "API Delete Test"

    # Delete it via DELETE /api/automations/{id}
    del_res = client.delete("/api/automations/auto_api_1", headers=headers)
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["status"] == "deleted"
    assert del_data["automation_id"] == "auto_api_1"

    # Verify it's gone
    get_after = client.get("/api/automations/auto_api_1", headers=headers)
    assert get_after.status_code == 404

    # Verify list is empty
    list_after = client.get("/api/automations", headers=headers)
    assert len(list_after.json()) == 0


def test_api_delete_nonexistent_automation_returns_404(client):
    headers = {
        "X-Organization-Id": "org-api-del",
        "X-User-Id": "user-del",
    }
    res = client.delete("/api/automations/missing_id", headers=headers)
    assert res.status_code == 404
    assert "not found" in res.json()["error"].lower()


# ==============================================================================
# 3. Disconnect Integration Completely Deletes All Related Data
# ==============================================================================

def test_disconnect_deletes_all_integration_data(tmp_path):
    store = IntegrationStateStore(tmp_path / "disc.sqlite3")
    mock_n8n = MagicMock()
    mock_n8n.delete_credential.return_value = {"success": True}

    manager = IntegrationManager(state_store=store)
    manager.n8n_client = mock_n8n

    # Connect Slack
    conn = manager.connect(
        organization_id="org-disc",
        integration="slack",
        secret="xoxb-dummy-secret-12345",
        account_identifier="#support-channel",
    )
    cred_ref_id = conn.credential_reference
    assert cred_ref_id != ""
    assert manager.credentials.resolve_credential("org-disc", cred_ref_id) == "xoxb-dummy-secret-12345"

    # Register n8n mapping
    manager.n8n_credential_provider.register_mapping(
        "org-disc", cred_ref_id, "n8n-cred-abc", "slack"
    )

    # Disconnect
    manager.disconnect("org-disc", "slack")

    # 1. Secret was completely deleted
    with pytest.raises(Exception):
        manager.credentials.resolve_credential("org-disc", cred_ref_id)

    # 2. Credential reference was deleted from the store
    assert store.get_credential_reference(cred_ref_id) is None

    # 3. n8n credential was deleted from n8n
    mock_n8n.delete_credential.assert_called_once_with("n8n-cred-abc")

    # 4. Connection status is disconnected and account info is cleared
    status = manager.connection_status("org-disc", "slack")
    assert status["status"] == "disconnected"
    assert status.get("account_identifier") is None
    assert status.get("credential_reference") == ""


def test_api_disconnect_purges_all_credentials_and_account_data(client):
    headers = {
        "X-Organization-Id": "org-api-disc",
        "X-User-Id": "user-disc",
    }

    # Connect CRM
    conn_res = client.post(
        "/api/integrations/crm/connect",
        json={"secret": "my-crm-api-key-999", "account_identifier": "sales-team"},
        headers=headers,
    )
    assert conn_res.status_code == 200

    # Verify connected
    list_res = client.get("/api/integrations", headers=headers)
    crm_entry = next(i for i in list_res.json() if i["integration"] == "crm")
    assert crm_entry["status"] == "connected"
    assert crm_entry["account_identifier"] == "sales-team"

    # Disconnect CRM
    disc_res = client.post("/api/integrations/crm/disconnect", headers=headers)
    assert disc_res.status_code == 200
    assert disc_res.json()["status"] == "disconnected"

    # Verify status is disconnected and account_identifier is purged
    list_after = client.get("/api/integrations", headers=headers)
    crm_after = next(i for i in list_after.json() if i["integration"] == "crm")
    assert crm_after["status"] == "disconnected"
    assert crm_after["account_identifier"] is None
    assert crm_after["connected_at"] is None
