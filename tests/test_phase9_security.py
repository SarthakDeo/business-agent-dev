from unittest.mock import MagicMock, patch

import pytest

from backend.agent.agent import Agent
from backend.agent.confirmation_manager import HighRiskBlockedError, evaluate_confirmation
from backend.agent.context_manager import ConversationContext
from backend.agent.permission_manager import PermissionDeniedError, check_permissions
from backend.agent.validator import ValidationError, validate_agent_plan
from backend.agent.workflow_compiler import (
    WorkflowCompilationError,
    WorkflowValidationError,
    WorkflowCompiler,
    WorkflowValidator,
)
from backend.agent.automation_manager import canonical_workflow_from_plan
from backend.integrations import IntegrationManager, IntegrationStateStore


def ask_write_plan():
    return {
        "mode": "ASK",
        "goal": "Find and update a customer",
        "steps": [{
            "id": "step_1",
            "tool": "crm.update_customer",
            "parameters": {
                "customer_id": "CUST-001",
                "updates": {"email": "new@example.com"},
            },
        }],
    }


def valid_workflow():
    return {
        "mode": "AUTOMATE",
        "name": "Safe workflow",
        "trigger": {"type": "webhook", "parameters": {}},
        "steps": [{
            "id": "step_1",
            "tool": "crm.find_order",
            "parameters": {"status": "delayed"},
        }],
    }


def test_unknown_tool_fails_closed_in_permission_gate():
    with pytest.raises(PermissionDeniedError):
        check_permissions({"steps": [{"id": "step_1", "tool": "unknown.tool"}]}, [], "user-a")


def test_missing_risk_classification_fails_closed():
    with patch("backend.agent.confirmation_manager.get_tool", return_value={"required_permission": "x"}):
        with pytest.raises(HighRiskBlockedError):
            evaluate_confirmation({"steps": [{"id": "step_1", "tool": "known.tool"}]})


def test_ask_write_tool_is_rejected_without_external_side_effect(tmp_path):
    manager = IntegrationManager(state_store=IntegrationStateStore(tmp_path / "state.sqlite3"))
    manager.connect("org-a", "crm", "FAKE_CRM_SECRET")
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=ask_write_plan()), \
         patch("backend.agent.execution_manager.dispatch_tool") as dispatch:
        result = agent.run("Find and update customer CUST-001", context, ["crm.write"])

    assert result.error_code == "INVALID_MODE"
    dispatch.assert_not_called()
    assert context.pending_steps == []


def test_unknown_parameter_is_rejected_before_execution(tmp_path):
    manager = IntegrationManager(state_store=IntegrationStateStore(tmp_path / "state.sqlite3"))
    manager.connect("org-a", "crm", "FAKE_CRM_SECRET")
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)
    plan = {
        "mode": "ASK",
        "goal": "Find orders",
        "steps": [{
            "id": "step_1",
            "tool": "crm.find_order",
            "parameters": {"status": "delayed", "arbitrary_url": "https://evil.invalid"},
        }],
    }

    with patch("backend.agent.agent.plan", return_value=plan), \
         patch("backend.agent.execution_manager.dispatch_tool") as dispatch:
        result = agent.run("Find delayed orders", context, ["crm.read"])

    assert result.error_code == "INVALID_PARAMETERS"
    dispatch.assert_not_called()


def test_model_cannot_supply_runtime_security_context():
    plan = {
        "mode": "ASK",
        "goal": "Read orders",
        "organization_id": "org-b",
        "steps": [{"id": "step_1", "tool": "crm.find_order", "parameters": {}}],
    }
    with pytest.raises(ValidationError):
        validate_agent_plan(plan)


def test_canonical_workflow_rejects_credential_like_fields():
    workflow = valid_workflow()
    workflow["steps"][0]["parameters"]["credential_id"] = "n8n-chosen-by-model"
    with pytest.raises(WorkflowValidationError) as error:
        WorkflowValidator().validate(workflow)
    assert error.value.code == "MISSING_CREDENTIAL"


def test_canonical_conversion_drops_raw_n8n_fields():
    plan = {
        "mode": "AUTOMATE",
        "goal": "Create a workflow",
        "trigger": {"type": "webhook", "parameters": {}},
        "nodes": [{"type": "n8n-nodes-base.httpRequest", "parameters": {"url": "https://evil.invalid"}}],
        "steps": [{"id": "step_1", "tool": "crm.find_order", "parameters": {}}],
    }
    canonical = canonical_workflow_from_plan(plan)
    assert "nodes" not in canonical
    assert "evil.invalid" not in str(canonical)


def test_legacy_compiler_rejects_raw_n8n_fields():
    manager = IntegrationManager()
    manager.connect("org-a", "crm", "FAKE_CRM_SECRET")
    with pytest.raises(WorkflowCompilationError) as error:
        WorkflowCompiler(manager).compile({
            "steps": [{
                "id": "step_1",
                "tool": "crm.find_order",
                "parameters": {"url": "https://evil.invalid"},
            }],
        }, "org-a")
    assert error.value.code == "INVALID_PARAMETER"


def test_automation_security_failure_does_not_call_n8n_or_persist(tmp_path):
    manager = IntegrationManager(state_store=IntegrationStateStore(tmp_path / "state.sqlite3"))
    manager.connect("org-a", "crm", "FAKE_CRM_SECRET")
    manager.connect("org-a", "slack", "FAKE_SLACK_SECRET")
    client = MagicMock()
    manager.n8n_client = client
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)
    plan = {
        "mode": "AUTOMATE",
        "goal": "Unsafe automation",
        "trigger": {"type": "webhook", "parameters": {}},
        "steps": [{
            "id": "step_1",
            "tool": "slack.send_message",
            "parameters": {"channel": "#support", "message": "ok", "token": "FAKE_SECRET"},
        }],
    }

    with patch("backend.agent.agent.plan", return_value=plan):
        result = agent.run("Create unsafe automation", context, ["slack.send"])

    assert result.status == "error"
    assert client.create_workflow.call_count == 0
    assert manager._state_store.list_automations("org-a") == []
