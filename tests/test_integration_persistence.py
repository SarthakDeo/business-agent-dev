import requests
import pytest
from unittest.mock import patch

from backend.agent.context_manager import ConversationContext
from backend.agent.execution_manager import execute_plan
from backend.agent.workflow_compiler import WorkflowCompiler
from backend.integrations import IntegrationManager, IntegrationStateStore


def _manager(path):
    return IntegrationManager(state_store=IntegrationStateStore(path))


def _slack_plan():
    return {
        "steps": [{
            "id": "step_1",
            "tool": "slack.send_message",
            "parameters": {"message": "persisted"},
        }]
    }


def test_connection_and_reference_survive_manager_reinitialization(tmp_path):
    path = tmp_path / "integration-state.sqlite3"
    first = _manager(path)
    connection = first.connect("org-a", "slack", "test-only-secret")

    second = _manager(path)
    restored = second.get_connection("org-a", "slack")

    assert restored.credential_reference == connection.credential_reference
    assert second.resolve_credential_reference("org-a", "slack").id == connection.credential_reference
    assert "test-only-secret" not in str(restored.safe_dict())


def test_persistence_enforces_tenant_isolation(tmp_path):
    path = tmp_path / "integration-state.sqlite3"
    manager = _manager(path)
    manager.connect("org-a", "slack", "secret-a")
    manager.connect("org-b", "slack", "secret-b")
    restored = _manager(path)

    assert restored.resolve_credential_reference("org-a", "slack").organization_id == "org-a"
    assert restored.resolve_credential_reference("org-b", "slack").organization_id == "org-b"
    assert (
        restored.resolve_credential_reference("org-a", "slack").id
        != restored.resolve_credential_reference("org-b", "slack").id
    )
    with pytest.raises(LookupError):
        restored.get_connection("org-c", "slack")


def test_disconnect_persists_and_blocks_execution(tmp_path):
    path = tmp_path / "integration-state.sqlite3"
    manager = _manager(path)
    manager.connect("org-a", "slack", "test-only-secret")
    manager.disconnect("org-a", "slack")
    restored = _manager(path)

    assert restored.get_connection("org-a", "slack").status == "disconnected"
    context = ConversationContext("user-a", "org-a", integration_manager=restored)
    context.approved_step_ids.add("step_1")
    with pytest.raises(Exception, match="Integration is not connected"):
        execute_plan(_slack_plan(), context)


def test_persisted_integration_is_used_by_compiler_and_execution(tmp_path):
    path = tmp_path / "integration-state.sqlite3"
    manager = _manager(path)
    connection = manager.connect("org-a", "slack", "test-only-secret")
    restored = _manager(path)

    compiled = WorkflowCompiler(restored).compile(_slack_plan(), "org-a")
    assert connection.credential_reference in str(compiled)
    assert "test-only-secret" not in str(compiled)

    context = ConversationContext("user-a", "org-a", integration_manager=restored)
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
