import requests
import pytest
from unittest.mock import patch

from backend.agent.context_manager import ConversationContext
from backend.agent.execution_manager import ExecutionError, execute_plan
from backend.agent.workflow_compiler import WorkflowCompilationError, WorkflowCompiler
from backend.integrations import IntegrationManager


def _slack_plan():
    return {
        "steps": [{
            "id": "step_1",
            "tool": "slack.send_message",
            "parameters": {"channel": "#support", "message": "hello"},
        }]
    }


def test_do_execution_resolves_reference_before_fallback():
    manager = IntegrationManager()
    connection = manager.connect("org-a", "slack", "test-secret")
    context = ConversationContext("user-a", "org-a", integration_manager=manager)
    context.approved_step_ids.add("step_1")

    with patch(
        "backend.agent.execution_manager._call_n8n",
        side_effect=requests.RequestException(),
    ), patch(
        "backend.agent.execution_manager.dispatch_tool",
        return_value={"success": True},
    ) as dispatch:
        execute_plan(_slack_plan(), context)

    assert dispatch.call_args.kwargs["credential_reference"] == connection.credential_reference
    assert dispatch.call_args.kwargs["organization_id"] == "org-a"


def test_do_execution_rejects_missing_integration():
    context = ConversationContext("user-a", "org-a")
    context.approved_step_ids.add("step_1")

    with pytest.raises(ExecutionError, match="Integration is not connected"):
        execute_plan(_slack_plan(), context)


def test_compiler_resolves_all_integrations_without_secrets():
    manager = IntegrationManager()
    slack = manager.connect("org-a", "slack", "slack-test-secret")
    crm = manager.connect("org-a", "crm", "crm-test-secret")
    workflow = {
        "mode": "AUTOMATE",
        "steps": [
            {"tool": "crm.create_ticket", "parameters": {}},
            {"tool": "slack.send_message", "parameters": {"message": "new ticket"}},
        ],
    }

    compiled = WorkflowCompiler(manager).compile(workflow, "org-a")

    assert compiled["credential_references"] == {
        "crm": crm.credential_reference,
        "slack": slack.credential_reference,
    }
    assert "slack-test-secret" not in str(compiled)
    assert "crm-test-secret" not in str(compiled)


def test_compiler_rejects_disconnected_tenant_integration():
    manager = IntegrationManager()
    manager.connect("org-a", "slack", "test-secret")
    manager.connect("org-b", "slack", "other-secret")

    with pytest.raises(WorkflowCompilationError):
        WorkflowCompiler(manager).compile(
            {"steps": [{"tool": "slack.send_message", "parameters": {}}]},
            "org-c",
        )

    assert (
        manager.resolve_credential_reference("org-a", "slack").id
        != manager.resolve_credential_reference("org-b", "slack").id
    )
