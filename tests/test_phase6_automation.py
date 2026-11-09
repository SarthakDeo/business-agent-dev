import pytest
from unittest.mock import MagicMock

from backend.agent.automation_manager import (
    AutomationCreationError,
    AutomationManager,
    canonical_workflow_from_plan,
)
from backend.integrations import IntegrationManager, IntegrationStateStore


def workflow_plan():
    return {
        "mode": "AUTOMATE",
        "goal": "Create a support automation",
        "automation_config": {
            "trigger_type": "webhook",
            "trigger_config": {"path": "customer-complaint"},
            "name": "Customer Complaint Automation",
        },
        "steps": [
            {
                "id": "create_ticket",
                "tool": "crm.create_ticket",
                "parameters": {
                    "customer_id": "{{trigger.customer_id}}",
                    "priority": "medium",
                    "title": "Customer complaint",
                    "description": "{{trigger.complaint}}",
                },
            },
            {
                "id": "notify_support",
                "tool": "slack.send_message",
                "parameters": {
                    "channel": "support",
                    "message": "New ticket: {{create_ticket.ticket_id}}",
                },
            },
        ],
    }


def configured_manager(tmp_path):
    manager = IntegrationManager(state_store=IntegrationStateStore(tmp_path / "state.sqlite3"))
    crm = manager.connect("org-a", "crm", "FAKE_CRM_SECRET")
    slack = manager.connect("org-a", "slack", "FAKE_SLACK_SECRET")
    client = MagicMock()
    client.create_workflow.return_value = {"id": "n8n-workflow-1"}
    manager.n8n_client = client
    manager.n8n_credential_provider.register_mapping("org-a", crm.credential_reference, "n8n-crm-1", "crm")
    manager.n8n_credential_provider.register_mapping("org-a", slack.credential_reference, "n8n-slack-1", "slack")
    return manager, client


def test_plan_converts_to_existing_canonical_workflow():
    canonical = canonical_workflow_from_plan(workflow_plan())
    assert canonical["mode"] == "AUTOMATE"
    assert canonical["trigger"]["type"] == "webhook"
    assert canonical["steps"][0]["id"] == "create_ticket"
    assert "goal" not in canonical
    assert "FAKE_CRM_SECRET" not in str(canonical)


def test_create_automation_compiles_creates_and_persists_mapping(tmp_path):
    manager, client = configured_manager(tmp_path)
    automation_manager = AutomationManager(integration_manager=manager)
    canonical = canonical_workflow_from_plan(workflow_plan())

    result = automation_manager.create_automation("org-a", canonical)

    assert result["status"] == "created"
    assert result["n8n_workflow_id"] == "n8n-workflow-1"
    created = client.create_workflow.call_args.args[0]
    assert created["nodes"][0]["type"] == "n8n-nodes-base.webhook"
    assert created["nodes"][1]["credentials"]["httpHeaderAuth"]["id"] == "n8n-crm-1"
    assert created["nodes"][2]["credentials"]["slackApi"]["id"] == "n8n-slack-1"
    assert "FAKE_CRM_SECRET" not in str(created)
    assert "FAKE_SLACK_SECRET" not in str(created)

    stored = manager._state_store.get_automation("org-a", result["automation_id"])
    assert stored["n8n_workflow_id"] == "n8n-workflow-1"
    assert stored["organization_id"] == "org-a"


def test_missing_integration_stops_before_n8n(tmp_path):
    manager = IntegrationManager(state_store=IntegrationStateStore(tmp_path / "state.sqlite3"))
    manager.connect("org-a", "crm", "FAKE_CRM_SECRET")
    client = MagicMock()
    manager.n8n_client = client
    automation_manager = AutomationManager(integration_manager=manager)

    with pytest.raises(AutomationCreationError) as error:
        automation_manager.create_automation("org-a", canonical_workflow_from_plan(workflow_plan()))

    assert error.value.code == "MISSING_INTEGRATION"
    client.create_workflow.assert_not_called()


def test_missing_credential_mapping_stops_before_n8n(tmp_path):
    manager = IntegrationManager(state_store=IntegrationStateStore(tmp_path / "state.sqlite3"))
    manager.connect("org-a", "crm", "FAKE_CRM_SECRET")
    manager.connect("org-a", "slack", "FAKE_SLACK_SECRET")
    client = MagicMock()
    manager.n8n_client = client
    automation_manager = AutomationManager(integration_manager=manager)

    with pytest.raises(AutomationCreationError) as error:
        automation_manager.create_automation("org-a", canonical_workflow_from_plan(workflow_plan()))

    assert error.value.code == "MISSING_CREDENTIAL"
    client.create_workflow.assert_not_called()


def test_wrong_tenant_cannot_create_automation(tmp_path):
    manager, client = configured_manager(tmp_path)
    automation_manager = AutomationManager(integration_manager=manager)

    with pytest.raises(AutomationCreationError) as error:
        automation_manager.create_automation("org-b", canonical_workflow_from_plan(workflow_plan()))

    assert error.value.code == "MISSING_INTEGRATION"
    client.create_workflow.assert_not_called()


def test_invalid_workflow_never_reaches_n8n(tmp_path):
    manager, client = configured_manager(tmp_path)
    automation_manager = AutomationManager(integration_manager=manager)
    invalid = canonical_workflow_from_plan(workflow_plan())
    invalid["steps"][1]["parameters"]["message"] = "{{missing.ticket_id}}"

    with pytest.raises(AutomationCreationError) as error:
        automation_manager.create_automation("org-a", invalid)

    assert error.value.code == "UNKNOWN_REFERENCE"
    client.create_workflow.assert_not_called()


def test_n8n_failure_is_normalized_without_raw_response(tmp_path):
    manager, client = configured_manager(tmp_path)
    client.create_workflow.side_effect = RuntimeError("fake-secret-from-provider")
    automation_manager = AutomationManager(integration_manager=manager)

    with pytest.raises(AutomationCreationError) as error:
        automation_manager.create_automation("org-a", canonical_workflow_from_plan(workflow_plan()))

    assert error.value.code == "N8N_CREATE_FAILED"
    assert "fake-secret-from-provider" not in str(error.value)
