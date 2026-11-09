"""Unit and integration tests for event triggers, variable references, and n8n trigger nodes."""

import pytest
from unittest.mock import patch

from backend.agent.planner import plan, _validate_plan_structure
from backend.agent.tool_registry import (
    get_tool,
    get_tool_kind,
    is_action_tool,
    is_trigger_tool,
    list_action_tools,
    list_all_tools,
    list_tools,
    list_trigger_tools,
    tool_exists,
)
from backend.agent.validator import (
    ValidationError,
    validate_agent_plan,
    validate_plan,
)
from backend.agent.workflow_compiler import (
    TRIGGER_NODE_MAPPINGS,
    WorkflowCompilationError,
    WorkflowCompiler,
    WorkflowValidationError,
    WorkflowValidator,
)
from backend.agent.automation_manager import canonical_workflow_from_plan
from backend.integrations import IntegrationManager


# ==============================================================================
# 1. Tool Registry Trigger vs Action Separation Tests
# ==============================================================================

def test_tool_registry_trigger_identification():
    assert is_trigger_tool("gmail.email_received") is True
    assert is_trigger_tool("slack.message_received") is True
    assert is_trigger_tool("schedule.daily") is True
    assert is_trigger_tool("schedule.weekly") is True
    assert is_trigger_tool("webhook.received") is True

    assert is_trigger_tool("gmail.send") is False
    assert is_trigger_tool("gmail.search") is False
    assert is_trigger_tool("slack.send_message") is False
    assert is_trigger_tool("crm.create_ticket") is False


def test_tool_registry_action_identification():
    assert is_action_tool("gmail.send") is True
    assert is_action_tool("gmail.search") is True
    assert is_action_tool("slack.send_message") is True
    assert is_action_tool("crm.create_ticket") is True

    assert is_action_tool("gmail.email_received") is False
    assert is_action_tool("slack.message_received") is False


def test_tool_registry_kinds():
    assert get_tool_kind("gmail.email_received") == "trigger"
    assert get_tool_kind("gmail.send") == "action"
    assert get_tool_kind("gmail.search") == "query"
    assert get_tool_kind("nonexistent.tool") == "unknown"


def test_tool_registry_lists():
    trigger_tools = list_trigger_tools()
    action_tools = list_action_tools()
    all_tools = list_all_tools()
    default_tools = list_tools()  # backward compatible: action tools only

    assert len(trigger_tools) == 5
    assert len(action_tools) == 10
    assert len(all_tools) == 15
    assert len(default_tools) == 10

    trigger_names = {t["name"] for t in trigger_tools}
    assert "gmail.email_received" in trigger_names
    assert "slack.message_received" in trigger_names
    assert "schedule.daily" in trigger_names
    assert "schedule.weekly" in trigger_names
    assert "webhook.received" in trigger_names


# ==============================================================================
# 2. Validator Trigger & Step Enforcement Tests
# ==============================================================================

def test_validator_rejects_action_as_trigger():
    bad_plan = {
        "mode": "AUTOMATE",
        "goal": "Invalid automation using action as trigger",
        "operation": "CREATE",
        "trigger": {
            "tool": "gmail.send",
            "type": "event",
            "parameters": {"to": "test@example.com", "subject": "hi", "body": "hi"},
        },
        "steps": [
            {
                "id": "step_1",
                "tool": "slack.send_message",
                "parameters": {"channel": "general", "message": "hello"},
            }
        ],
    }
    with pytest.raises(ValidationError) as exc:
        validate_agent_plan(bad_plan)
    assert "Action tool 'gmail.send' cannot be used as a trigger" in str(exc.value)


def test_validator_rejects_trigger_as_step():
    bad_plan = {
        "mode": "AUTOMATE",
        "goal": "Invalid automation using trigger as step",
        "operation": "CREATE",
        "trigger": {
            "tool": "gmail.email_received",
            "type": "event",
            "parameters": {},
        },
        "steps": [
            {
                "id": "step_1",
                "tool": "gmail.email_received",
                "parameters": {},
            }
        ],
    }
    with pytest.raises(ValidationError) as exc:
        validate_agent_plan(bad_plan)
    assert "Trigger tool 'gmail.email_received' cannot be used as an action step" in str(exc.value)


def test_validator_rejects_unknown_trigger_tool():
    bad_plan = {
        "mode": "AUTOMATE",
        "goal": "Invalid automation using unknown trigger",
        "operation": "CREATE",
        "trigger": {
            "tool": "unknown.custom_trigger",
            "type": "event",
            "parameters": {},
        },
        "steps": [
            {
                "id": "step_1",
                "tool": "slack.send_message",
                "parameters": {"channel": "general", "message": "hello"},
            }
        ],
    }
    with pytest.raises(ValidationError) as exc:
        validate_agent_plan(bad_plan)
    assert "Trigger tool 'unknown.custom_trigger' is not registered" in str(exc.value)


# ==============================================================================
# 3. Workflow Validator Reference Enforcement Tests
# ==============================================================================

def test_workflow_validator_rejects_unnamespaced_reference():
    workflow = {
        "mode": "AUTOMATE",
        "name": "Invalid Bare Reference Workflow",
        "trigger": {
            "tool": "gmail.email_received",
            "type": "event",
            "parameters": {},
        },
        "steps": [
            {
                "id": "step_1",
                "tool": "gmail.send",
                "parameters": {
                    "to": "test@example.com",
                    "subject": "{{subject}}",  # BARE REFERENCE (INVALID)
                    "body": "Thank you for reaching out.",
                },
            }
        ],
    }
    with pytest.raises(WorkflowValidationError) as exc:
        WorkflowValidator().validate(workflow)
    assert exc.value.code == "INVALID_REFERENCE"
    assert "Invalid reference '{{subject}}'" in str(exc.value)


def test_workflow_validator_rejects_nonexistent_trigger_field():
    workflow = {
        "mode": "AUTOMATE",
        "name": "Invalid Trigger Field Workflow",
        "trigger": {
            "tool": "gmail.email_received",
            "type": "event",
            "parameters": {},
        },
        "steps": [
            {
                "id": "step_1",
                "tool": "gmail.send",
                "parameters": {
                    "to": "{{trigger.from}}",
                    "subject": "Re: {{trigger.subject}}",
                    "body": "{{trigger.nonexistent_field}}",  # DOES NOT EXIST ON GMAIL TRIGGER
                },
            }
        ],
    }
    with pytest.raises(WorkflowValidationError) as exc:
        WorkflowValidator().validate(workflow)
    assert exc.value.code == "UNKNOWN_REFERENCE"
    assert "Unknown output field 'nonexistent_field' on 'trigger'" in str(exc.value)


def test_workflow_validator_accepts_valid_trigger_references():
    workflow = {
        "mode": "AUTOMATE",
        "name": "Auto-Reply Email Workflow",
        "trigger": {
            "tool": "gmail.email_received",
            "type": "event",
            "parameters": {"read_status": "unread"},
        },
        "steps": [
            {
                "id": "step_1",
                "tool": "gmail.send",
                "parameters": {
                    "to": "{{trigger.from}}",
                    "subject": "Re: {{trigger.subject}}",
                    "body": "Thanks for contacting us! We received your message and will get back shortly.",
                    "thread_id": "{{trigger.thread_id}}",
                },
            }
        ],
    }
    validated = WorkflowValidator().validate(workflow)
    assert validated["mode"] == "AUTOMATE"


# ==============================================================================
# 4. Compiler Native n8n Node Generation Tests
# ==============================================================================

def test_compiler_compiles_gmail_trigger_and_action():
    manager = IntegrationManager()
    manager.connect("org-test", "gmail", "FAKE_GMAIL_TOKEN")

    workflow = {
        "mode": "AUTOMATE",
        "name": "Auto-Reply Email Workflow",
        "trigger": {
            "tool": "gmail.email_received",
            "type": "event",
            "parameters": {"read_status": "unread"},
        },
        "steps": [
            {
                "id": "reply_step",
                "tool": "gmail.send",
                "parameters": {
                    "to": "{{trigger.from}}",
                    "subject": "Re: {{trigger.subject}}",
                    "body": "Thank you for contacting us.",
                    "thread_id": "{{trigger.thread_id}}",
                },
            }
        ],
    }

    compiler = WorkflowCompiler(manager)
    compiled = compiler.compile(workflow, "org-test")

    # Check Trigger Node
    trigger_node = compiled["nodes"][0]
    assert trigger_node["name"] == "Trigger"
    assert trigger_node["type"] == "n8n-nodes-base.gmailTrigger"
    assert trigger_node["typeVersion"] == 1
    assert trigger_node["parameters"]["event"] == "messageReceived"
    assert trigger_node["parameters"]["authentication"] == "oAuth2"
    assert trigger_node["parameters"]["simple"] is False
    assert trigger_node["parameters"]["filters"] == {"readStatus": "unread"}
    assert "gmailOAuth2" in trigger_node["credentials"]

    # Check Step Node
    step_node = compiled["nodes"][1]
    assert step_node["name"] == "reply_step"
    assert step_node["type"] == "n8n-nodes-base.gmail"
    assert step_node["parameters"]["operation"] == "send"
    assert "gmailOAuth2" in step_node["credentials"]

    # Check Expressions
    assert "Trigger" in step_node["parameters"]["toEmail"]
    assert "threadId" in step_node["parameters"]["options"]["threadId"]

    # Check Connection
    assert compiled["connections"]["Trigger"]["main"][0][0]["node"] == "reply_step"


def test_compiler_compiles_slack_trigger_and_schedule_trigger():
    manager = IntegrationManager()
    manager.connect("org-test", "slack", "FAKE_SLACK_TOKEN")

    # Slack message trigger -> Slack response
    slack_wf = {
        "mode": "AUTOMATE",
        "name": "Slack Alert Automation",
        "trigger": {
            "tool": "slack.message_received",
            "type": "event",
            "parameters": {"channel": "alerts"},
        },
        "steps": [
            {
                "id": "notify",
                "tool": "slack.send_message",
                "parameters": {
                    "channel": "dev-team",
                    "message": "Received alert: {{trigger.text}}",
                },
            }
        ],
    }

    compiler = WorkflowCompiler(manager)
    compiled = compiler.compile(slack_wf, "org-test")

    trigger_node = compiled["nodes"][0]
    assert trigger_node["type"] == "n8n-nodes-base.slackTrigger"
    assert trigger_node["parameters"]["event"] == "message"
    assert trigger_node["parameters"]["channel"] == "alerts"
    assert "slackApi" in trigger_node["credentials"]

    # Schedule trigger -> daily report
    daily_wf = {
        "mode": "AUTOMATE",
        "name": "Daily Digest",
        "trigger": {
            "tool": "schedule.daily",
            "type": "schedule",
            "parameters": {"hour": 9, "minute": 30},
        },
        "steps": [
            {
                "id": "post_digest",
                "tool": "slack.send_message",
                "parameters": {
                    "channel": "general",
                    "message": "Good morning team!",
                },
            }
        ],
    }

    compiled_daily = compiler.compile(daily_wf, "org-test")
    schedule_node = compiled_daily["nodes"][0]
    assert schedule_node["type"] == "n8n-nodes-base.scheduleTrigger"
    assert schedule_node["parameters"]["rule"]["interval"][0]["triggerAtHour"] == 9
    assert schedule_node["parameters"]["rule"]["interval"][0]["triggerAtMinute"] == 30
    assert "credentials" not in schedule_node  # schedule needs no external credentials


# ==============================================================================
# 5. Planner Prompt / Plan Classification & Regression Tests
# ==============================================================================

def test_plan_structure_preserves_event_trigger():
    raw_plan = {
        "mode": "AUTOMATE",
        "goal": "Auto-reply to incoming emails",
        "operation": "CREATE",
        "trigger": {
            "tool": "gmail.email_received",
            "type": "event",
            "parameters": {"read_status": "unread"},
        },
        "steps": [
            {
                "id": "step_1",
                "tool": "gmail.send",
                "parameters": {
                    "to": "{{trigger.from}}",
                    "subject": "Re: {{trigger.subject}}",
                    "body": "Thanks for contacting us! We have received your message.",
                    "thread_id": "{{trigger.thread_id}}",
                },
            }
        ],
    }

    _validate_plan_structure(raw_plan)
    assert raw_plan["mode"] == "AUTOMATE"
    assert raw_plan["trigger"]["tool"] == "gmail.email_received"
    assert raw_plan["trigger"]["type"] == "event"

    canonical = canonical_workflow_from_plan(raw_plan)
    assert canonical["trigger"]["tool"] == "gmail.email_received"
    assert canonical["trigger"]["type"] == "event"


def test_one_time_action_uses_do_mode():
    """Verify that a one-time request like 'Send John an email' produces DO mode without triggers."""
    one_time_plan = {
        "mode": "DO",
        "goal": "Send John an email",
        "steps": [
            {
                "id": "step_1",
                "tool": "gmail.send",
                "parameters": {
                    "to": "john@example.com",
                    "subject": "Status Update",
                    "body": "Hi John, here is the update.",
                },
            }
        ],
    }

    _validate_plan_structure(one_time_plan)
    assert one_time_plan["mode"] == "DO"
    assert "trigger" not in one_time_plan or one_time_plan["trigger"] is None


def test_automation_manager_confirmation_summary_displays_trigger():
    from backend.agent.automation_manager import AutomationManager

    workflow = {
        "mode": "AUTOMATE",
        "name": "Auto-Reply Email Workflow",
        "trigger": {
            "tool": "gmail.email_received",
            "type": "event",
            "parameters": {},
        },
        "steps": [
            {
                "id": "reply_step",
                "tool": "gmail.send",
                "parameters": {
                    "to": "test@example.com",
                    "subject": "Re: Inquiry",
                    "body": "Thank you for contacting us.",
                },
            }
        ],
    }

    manager = AutomationManager()
    summary = manager.confirmation_summary(workflow)
    assert "Gmail" in summary
    assert "Trigger: Gmail — Runs when a new email is received in Gmail" in summary
    assert "1. gmail.send to test@example.com" in summary


def test_automation_manager_creation_checks_trigger_credentials():
    from backend.agent.automation_manager import AutomationCreationError, AutomationManager

    manager = IntegrationManager()
    # Connect only slack, NOT gmail
    manager.connect("org-no-gmail", "slack", "FAKE_SLACK_SECRET")

    workflow = {
        "mode": "AUTOMATE",
        "name": "Incoming Email to Slack",
        "trigger": {
            "tool": "gmail.email_received",
            "type": "event",
            "parameters": {},
        },
        "steps": [
            {
                "id": "step_1",
                "tool": "slack.send_message",
                "parameters": {
                    "channel": "general",
                    "message": "New email from {{trigger.from}}",
                },
            }
        ],
    }

    auto_mgr = AutomationManager(integration_manager=manager)
    with pytest.raises(AutomationCreationError) as exc:
        auto_mgr.validate_for_creation("org-no-gmail", workflow)
    assert exc.value.code == "MISSING_INTEGRATION"
    assert "Integration 'gmail' is not connected" in str(exc.value)

