from unittest.mock import MagicMock, patch

import requests

from backend.agent.agent import Agent
from backend.agent.context_manager import ConversationContext
from backend.integrations import IntegrationManager, IntegrationStateStore


def do_plan():
    return {
        "mode": "DO",
        "goal": "Notify support",
        "steps": [{
            "id": "step_1",
            "tool": "slack.send_message",
            "parameters": {"channel": "#support", "message": "Deployment complete."},
        }],
    }


def ask_plan():
    return {
        "mode": "ASK",
        "goal": "Count delayed orders",
        "steps": [{
            "id": "step_1",
            "tool": "crm.find_order",
            "parameters": {"status": "delayed"},
        }],
    }


def automate_plan():
    return {
        "mode": "AUTOMATE",
        "goal": "Notify support when complaints arrive",
        "name": "Complaint Support Automation",
        "trigger": {"type": "webhook", "parameters": {"event": "complaint"}},
        "steps": [{
            "id": "notify_support",
            "tool": "slack.send_message",
            "parameters": {"channel": "#support", "message": "New complaint"},
        }],
    }


def agent_with_manager(tmp_path, n8n_client=None):
    manager = IntegrationManager(state_store=IntegrationStateStore(tmp_path / "state.sqlite3"))
    manager.connect("org-a", "crm", "FAKE_CRM_SECRET")
    manager.connect("org-a", "slack", "FAKE_SLACK_SECRET")
    if n8n_client is not None:
        manager.n8n_client = n8n_client
        reference = manager.resolve_credential_reference("org-a", "slack")
        manager.n8n_credential_provider.register_mapping(
            "org-a", reference.id, "n8n-slack-1", "slack"
        )
    return Agent(manager), manager


def test_ask_routes_to_one_time_execution_and_never_automation(tmp_path):
    agent, manager = agent_with_manager(tmp_path)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=ask_plan()), \
         patch("backend.agent.execution_manager._call_n8n", side_effect=requests.RequestException()), \
         patch("backend.agent.execution_manager.dispatch_tool", return_value={"success": True, "count": 2}) as dispatch, \
         patch.object(agent.automation_manager, "create_automation") as create:
        result = agent.run("How many delayed orders are there?", context, ["crm.read"])

    assert result.mode == "ASK"
    assert result.status == "completed"
    dispatch.assert_called_once()
    create.assert_not_called()


def test_do_requires_confirmation_then_executes_once(tmp_path):
    agent, manager = agent_with_manager(tmp_path)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=do_plan()), \
         patch("backend.agent.execution_manager._call_n8n", side_effect=requests.RequestException()), \
         patch("backend.agent.execution_manager.dispatch_tool", return_value={"success": True, "ok": True}) as dispatch:
        pending = agent.run("Send a Slack message to support.", context, ["slack.send"])
        approved = agent.resume_confirmation(context, approved=True)
        second_approval = agent.resume_confirmation(context, approved=True)

    assert pending.mode == "DO"
    assert pending.status == "awaiting_confirmation"
    assert approved.status == "completed"
    assert second_approval.response_text.startswith("No pending actions")
    dispatch.assert_called_once()


def test_do_rejection_does_not_execute(tmp_path):
    agent, manager = agent_with_manager(tmp_path)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=do_plan()), \
         patch("backend.agent.execution_manager.dispatch_tool") as dispatch:
        agent.run("Send a Slack message.", context, ["slack.send"])
        rejected = agent.resume_confirmation(context, approved=False)

    assert rejected.mode == "DO"
    assert rejected.error_code == "CONFIRMATION_REJECTED"
    dispatch.assert_not_called()


def test_automation_cannot_execute_before_confirmation_or_twice(tmp_path):
    client = MagicMock()
    client.create_workflow.return_value = {"id": "n8n-workflow-7"}
    agent, manager = agent_with_manager(tmp_path, client)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=automate_plan()):
        pending = agent.run("Whenever a complaint arrives, notify support.", context, ["slack.send"])
        assert pending.mode == "AUTOMATE"
        assert pending.status == "awaiting_confirmation"
        client.create_workflow.assert_not_called()

        approved = agent.resume_confirmation(context, approved=True)
        second_approval = agent.resume_confirmation(context, approved=True)

    assert approved.mode == "AUTOMATE"
    assert approved.status == "completed"
    assert "n8n Workflow ID: n8n-workflow-7" in approved.response_text
    assert second_approval.response_text.startswith("No pending actions")
    client.create_workflow.assert_called_once()


def test_pending_operation_cannot_be_overwritten_by_new_mode(tmp_path):
    agent, manager = agent_with_manager(tmp_path)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", side_effect=[do_plan(), automate_plan()]) as planner:
        pending = agent.run("Send a Slack message.", context, ["slack.send"])
        blocked = agent.run("Create an automation instead.", context, ["slack.send"])

    assert pending.mode == "DO"
    assert blocked.mode == "DO"
    assert blocked.status == "awaiting_confirmation"
    assert blocked.error_code == "CONFIRMATION_REQUIRED"
    assert planner.call_count == 1


def test_confirmation_fallback_mentions_mode_specific_action(tmp_path):
    agent, manager = agent_with_manager(tmp_path)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=do_plan()), \
         patch("backend.agent.response_generator.genai", None):
        result = agent.run("Send a Slack message.", context, ["slack.send"])

    assert "Please confirm" in result.response_text
    assert "slack.send_message" in result.response_text
