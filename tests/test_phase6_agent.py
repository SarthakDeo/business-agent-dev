import json
from unittest.mock import MagicMock, patch

from backend.agent.agent import Agent
from backend.agent.context_manager import ConversationContext
from backend.integrations import IntegrationManager, IntegrationStateStore


def automate_plan():
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


def configured_agent(tmp_path):
    manager = IntegrationManager(state_store=IntegrationStateStore(tmp_path / "state.sqlite3"))
    crm = manager.connect("org-a", "crm", "FAKE_CRM_SECRET")
    slack = manager.connect("org-a", "slack", "FAKE_SLACK_SECRET")
    client = MagicMock()
    client.create_workflow.return_value = {"id": "n8n-workflow-1"}
    manager.n8n_client = client
    manager.n8n_credential_provider.register_mapping("org-a", crm.credential_reference, "n8n-crm-1", "crm")
    manager.n8n_credential_provider.register_mapping("org-a", slack.credential_reference, "n8n-slack-1", "slack")
    return Agent(manager), manager, client


def test_automate_waits_for_confirmation_then_creates_workflow(tmp_path):
    agent, manager, client = configured_agent(tmp_path)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=automate_plan()):
        pending = agent.run(
            "Whenever a customer complains, create a CRM ticket and notify support on Slack.",
            context,
            ["crm.write", "slack.send"],
        )

    assert pending.mode == "AUTOMATE"
    assert pending.status == "awaiting_confirmation"
    client.create_workflow.assert_not_called()
    assert context.pending_automation_workflow["mode"] == "AUTOMATE"

    approved = agent.resume_confirmation(context, approved=True)

    assert approved.status == "completed"
    assert approved.execution_results["automation"]["n8n_workflow_id"] == "n8n-workflow-1"
    client.create_workflow.assert_called_once()
    assert "FAKE_CRM_SECRET" not in str(client.create_workflow.call_args)
    assert "FAKE_SLACK_SECRET" not in str(client.create_workflow.call_args)


def test_rejected_automation_never_calls_n8n(tmp_path):
    agent, manager, client = configured_agent(tmp_path)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=automate_plan()):
        pending = agent.run("Create a complaint automation", context, ["crm.write", "slack.send"])

    rejected = agent.resume_confirmation(context, approved=False)

    assert pending.status == "awaiting_confirmation"
    assert rejected.status == "cancelled"
    client.create_workflow.assert_not_called()
    assert context.pending_automation_workflow is None


def test_invalid_automate_plan_is_rejected_before_confirmation_or_n8n(tmp_path):
    agent, manager, client = configured_agent(tmp_path)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)
    invalid = automate_plan()
    invalid["steps"][1]["parameters"]["message"] = "{{missing.ticket_id}}"

    with patch("backend.agent.agent.plan", return_value=invalid):
        result = agent.run("Create a complaint automation", context, ["crm.write", "slack.send"])

    assert result.status == "error"
    assert client.create_workflow.call_count == 0
    assert context.pending_automation_workflow is None


def test_planner_accepts_automate_structured_output():
    response = MagicMock()
    response.text = json.dumps(automate_plan())
    chat = MagicMock()
    chat.send_message.return_value = response

    with patch("backend.agent.planner.genai") as genai, patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
        genai.Client.return_value.chats.create.return_value = chat
        from backend.agent.planner import plan

        result = plan("Whenever a customer complains, notify support.")

    assert result["mode"] == "AUTOMATE"
    assert result["automation_config"]["trigger_type"] == "webhook"


def test_planner_accepts_canonical_automate_trigger():
    plan_with_trigger = automate_plan()
    plan_with_trigger.pop("automation_config")
    plan_with_trigger["name"] = "Customer Complaint Automation"
    plan_with_trigger["trigger"] = {
        "type": "webhook",
        "parameters": {"event": "customer_complaint"},
    }
    response = MagicMock()
    response.text = json.dumps(plan_with_trigger)
    chat = MagicMock()
    chat.send_message.return_value = response

    with patch("backend.agent.planner.genai") as genai, patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
        genai.Client.return_value.chats.create.return_value = chat
        from backend.agent.planner import plan

        result = plan("Create a customer complaint automation.")

    assert result["trigger"]["type"] == "webhook"
