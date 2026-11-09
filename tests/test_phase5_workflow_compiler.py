import pytest

from backend.agent.workflow_compiler import (
    WorkflowCompilationError,
    WorkflowCompiler,
    WorkflowValidationError,
    WorkflowValidator,
)
from backend.integrations import IntegrationManager, N8nClient, N8nConfig


class FakeResponse:
    status_code = 200

    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return FakeResponse(next(self.responses))


def canonical_workflow():
    return {
        "mode": "AUTOMATE",
        "name": "Customer Complaint Automation",
        "trigger": {
            "type": "webhook",
            "parameters": {"path": "customer-complaint"},
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
                "id": "notify_slack",
                "tool": "slack.send_message",
                "parameters": {
                    "channel": "support",
                    "message": "New ticket: {{create_ticket.ticket_id}}",
                },
            },
        ],
    }


def connected_manager():
    manager = IntegrationManager()
    crm = manager.connect("org-a", "crm", "FAKE_CRM_SECRET")
    slack = manager.connect("org-a", "slack", "FAKE_SLACK_SECRET")
    return manager, crm, slack


def test_valid_canonical_workflow_compiles_to_connected_graph():
    manager, crm, slack = connected_manager()
    compiled = WorkflowCompiler(manager).compile(canonical_workflow(), "org-a")

    assert [node["name"] for node in compiled["nodes"]] == [
        "Trigger", "create_ticket", "notify_slack"
    ]
    assert compiled["nodes"][0]["type"] == "n8n-nodes-base.webhook"
    assert compiled["nodes"][1]["type"] == "n8n-nodes-base.httpRequest"
    assert compiled["nodes"][2]["type"] == "n8n-nodes-base.slack"
    assert compiled["connections"]["Trigger"]["main"][0][0]["node"] == "create_ticket"
    assert compiled["connections"]["create_ticket"]["main"][0][0]["node"] == "notify_slack"
    assert compiled["credential_references"] == {"crm": crm.credential_reference, "slack": slack.credential_reference}
    assert compiled["nodes"][1]["parameters"]["input"]["customer_id"] == '={{$node["Trigger"].json["customer_id"]}}'
    assert "FAKE_CRM_SECRET" not in str(compiled)
    assert "FAKE_SLACK_SECRET" not in str(compiled)


def test_compiler_resolves_real_n8n_credential_ids_when_client_is_configured():
    manager, crm, slack = connected_manager()
    manager.n8n_client = object()
    manager.n8n_credential_provider.register_mapping("org-a", crm.credential_reference, "n8n-crm-1", "crm")
    manager.n8n_credential_provider.register_mapping("org-a", slack.credential_reference, "n8n-slack-1", "slack")

    compiled = WorkflowCompiler(manager).compile(canonical_workflow(), "org-a")

    assert compiled["credential_references"] == {"crm": "n8n-crm-1", "slack": "n8n-slack-1"}
    assert compiled["nodes"][1]["credentials"]["httpHeaderAuth"]["id"] == "n8n-crm-1"
    assert compiled["nodes"][2]["credentials"]["slackApi"]["id"] == "n8n-slack-1"


def test_gmail_send_uses_centralized_gmail_mapping():
    manager = IntegrationManager()
    manager.connect("org-a", "gmail", "FAKE_GMAIL_SECRET")
    workflow = canonical_workflow()
    workflow["steps"] = [{
        "id": "send_email",
        "tool": "gmail.send",
        "parameters": {
            "to": "support@example.com",
            "subject": "Complaint received",
            "body": "{{trigger.complaint}}",
        },
    }]

    compiled = WorkflowCompiler(manager).compile(workflow, "org-a")

    assert compiled["nodes"][1]["type"] == "n8n-nodes-base.gmail"
    assert compiled["nodes"][1]["credentials"]["gmailOAuth2"]["id"]


def test_compiled_workflow_can_be_sent_through_existing_n8n_client():
    manager, _, _ = connected_manager()
    compiled = WorkflowCompiler(manager).compile(canonical_workflow(), "org-a")
    session = FakeSession([{"id": "workflow-1", "name": compiled["name"]}])
    client = N8nClient(N8nConfig("http://n8n.test", "fake-key"), session)

    result = client.create_workflow(compiled)

    assert result["id"] == "workflow-1"
    assert session.calls[0][0:2] == ("POST", "http://n8n.test/api/v1/workflows")
    assert session.calls[0][2]["json"] == compiled


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (lambda workflow: workflow["steps"].append(workflow["steps"][0].copy()), "INVALID_WORKFLOW"),
        (lambda workflow: workflow["steps"][0].update({"tool": "unknown.tool"}), "UNKNOWN_TOOL"),
        (lambda workflow: workflow["steps"][0].update({"parameters": {"priority": "normal"}}), "INVALID_PARAMETER"),
        (lambda workflow: workflow["steps"][1]["parameters"].update({"message": "{{missing.ticket_id}}"}), "UNKNOWN_REFERENCE"),
        (lambda workflow: workflow["steps"][0]["parameters"].update({"api_key": "FAKE_SECRET"}), "MISSING_CREDENTIAL"),
    ],
)
def test_invalid_canonical_workflows_are_rejected(mutator, code):
    workflow = canonical_workflow()
    mutator(workflow)
    with pytest.raises(WorkflowValidationError) as error:
        WorkflowValidator().validate(workflow)
    assert error.value.code == code


def test_missing_trigger_is_rejected_by_validator():
    workflow = canonical_workflow()
    workflow.pop("trigger")
    with pytest.raises(WorkflowValidationError) as error:
        WorkflowValidator().validate(workflow)
    assert error.value.code == "INVALID_WORKFLOW"


def test_wrong_tenant_or_missing_n8n_mapping_fails_safely():
    manager, crm, _ = connected_manager()
    manager.n8n_client = object()
    manager.n8n_credential_provider.register_mapping("org-a", crm.credential_reference, "n8n-crm-1", "crm")

    with pytest.raises(WorkflowCompilationError) as error:
        WorkflowCompiler(manager).compile(canonical_workflow(), "org-b")
    assert error.value.code == "MISSING_CREDENTIAL"
    assert "FAKE_CRM_SECRET" not in str(error.value)
