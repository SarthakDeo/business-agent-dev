from copy import deepcopy
from unittest.mock import MagicMock, patch
import pytest
import requests

from backend.agent.agent import Agent
from backend.agent.automation_manager import (
    AutomationAmbiguousError,
    AutomationCreationError,
    AutomationManager,
    AutomationNotFoundError,
    InvalidModificationError,
    apply_modification,
)
from backend.agent.context_manager import ConversationContext
from backend.agent.planner import _validate_plan_structure
from backend.agent.validator import ValidationError, validate_agent_plan
from backend.integrations import IntegrationManager, IntegrationStateStore, N8nClient, N8nConfig


def sample_canonical_workflow():
    return {
        "mode": "AUTOMATE",
        "name": "Customer Support Workflow",
        "trigger": {
            "type": "webhook",
            "parameters": {"path": "customer-complaint"},
        },
        "steps": [
            {
                "id": "step_crm",
                "tool": "crm.create_ticket",
                "parameters": {
                    "customer_id": "{{trigger.customer_id}}",
                    "priority": "medium",
                    "title": "Complaint",
                    "description": "Urgent issue",
                },
            },
            {
                "id": "step_slack",
                "tool": "slack.send_message",
                "parameters": {
                    "channel": "#support",
                    "message": "New ticket created",
                },
            },
        ],
    }


def configured_manager(tmp_path, n8n_client=None):
    store = IntegrationStateStore(tmp_path / "state.sqlite3")
    manager = IntegrationManager(state_store=store)
    crm = manager.connect("org-a", "crm", "FAKE_CRM_SECRET")
    slack = manager.connect("org-a", "slack", "FAKE_SLACK_SECRET")
    gmail = manager.connect("org-a", "gmail", "FAKE_GMAIL_SECRET")

    client = n8n_client or MagicMock()
    if n8n_client is None:
        client.create_workflow.return_value = {"id": "n8n-wf-100"}
        client.update_workflow.return_value = {"id": "n8n-wf-100", "name": "Customer Support Workflow"}
    manager.n8n_client = client

    manager.n8n_credential_provider.register_mapping("org-a", crm.credential_reference, "n8n-crm-1", "crm")
    manager.n8n_credential_provider.register_mapping("org-a", slack.credential_reference, "n8n-slack-1", "slack")
    manager.n8n_credential_provider.register_mapping("org-a", gmail.credential_reference, "n8n-gmail-1", "gmail")
    return manager, client, store


def seed_automation(store, org_id="org-a", auto_id="auto_123", name="Customer Support Workflow", n8n_id="n8n-wf-100"):
    record = {
        "id": auto_id,
        "organization_id": org_id,
        "n8n_workflow_id": n8n_id,
        "name": name,
        "status": "created",
        "canonical_workflow": sample_canonical_workflow(),
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    store.save_automation(record)
    return record


# -------------------------------------------------------------------------
# Test Cases 1-4: Identification and Lookup
# -------------------------------------------------------------------------

def test_lookup_by_automation_id(tmp_path):
    manager, _, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Support Workflow")
    auto_mgr = AutomationManager(manager)

    found = auto_mgr.find_automation("org-a", "auto_123")
    assert found["id"] == "auto_123"
    assert found["name"] == "Support Workflow"


def test_lookup_by_name_exact(tmp_path):
    manager, _, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow")
    auto_mgr = AutomationManager(manager)

    found = auto_mgr.find_automation("org-a", "customer support workflow")
    assert found["id"] == "auto_123"


def test_lookup_by_name_fuzzy(tmp_path):
    manager, _, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow")
    auto_mgr = AutomationManager(manager)

    found = auto_mgr.find_automation("org-a", "support")
    assert found["id"] == "auto_123"


def test_lookup_not_found_raises_structured_error(tmp_path):
    manager, _, store = configured_manager(tmp_path)
    auto_mgr = AutomationManager(manager)

    with pytest.raises(AutomationNotFoundError) as exc_info:
        auto_mgr.find_automation("org-a", "non_existent_auto")
    assert exc_info.value.code == "AUTOMATION_NOT_FOUND"


def test_lookup_ambiguous_raises_structured_error(tmp_path):
    manager, _, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_1", "Support Workflow 1")
    seed_automation(store, "org-a", "auto_2", "Support Workflow 2")
    auto_mgr = AutomationManager(manager)

    with pytest.raises(AutomationAmbiguousError) as exc_info:
        auto_mgr.find_automation("org-a", "support")
    assert exc_info.value.code == "AUTOMATION_AMBIGUOUS"
    assert len(exc_info.value.matches) == 2


def test_tenant_isolation_lookup(tmp_path):
    manager, _, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Support Workflow")
    auto_mgr = AutomationManager(manager)

    # org-b should not find org-a's automation by ID or name
    with pytest.raises(AutomationNotFoundError):
        auto_mgr.find_automation("org-b", "auto_123")

    with pytest.raises(AutomationNotFoundError):
        auto_mgr.find_automation("org-b", "Support Workflow")


# -------------------------------------------------------------------------
# Test Cases 8-11: Canonical Modification Operations
# -------------------------------------------------------------------------

def test_apply_modification_add_step():
    wf = sample_canonical_workflow()
    mod = {
        "operation": "ADD_STEP",
        "step": {
            "id": "step_gmail",
            "tool": "gmail.send",
            "parameters": {"to": "ops@example.com", "subject": "Ticket", "body": "Details"},
        },
    }
    result = apply_modification(wf, mod)
    assert len(result["steps"]) == 3
    assert result["steps"][-1]["id"] == "step_gmail"
    assert result["steps"][-1]["tool"] == "gmail.send"


def test_apply_modification_add_step_with_position():
    wf = sample_canonical_workflow()
    mod = {
        "operation": "ADD_STEP",
        "insert_at": 1,
        "step": {
            "id": "step_gmail",
            "tool": "gmail.send",
            "parameters": {"to": "ops@example.com", "subject": "Ticket", "body": "Details"},
        },
    }
    result = apply_modification(wf, mod)
    assert len(result["steps"]) == 3
    assert result["steps"][1]["id"] == "step_gmail"


def test_apply_modification_remove_step():
    wf = sample_canonical_workflow()
    mod = {
        "operation": "REMOVE_STEP",
        "step_id": "step_slack",
    }
    result = apply_modification(wf, mod)
    assert len(result["steps"]) == 1
    assert result["steps"][0]["id"] == "step_crm"


def test_apply_modification_replace_step():
    wf = sample_canonical_workflow()
    mod = {
        "operation": "REPLACE_STEP",
        "step_id": "step_slack",
        "step": {
            "id": "step_slack",
            "tool": "gmail.send",
            "parameters": {"to": "team@example.com", "subject": "Alert", "body": "Complaint"},
        },
    }
    result = apply_modification(wf, mod)
    assert len(result["steps"]) == 2
    assert result["steps"][1]["id"] == "step_slack"
    assert result["steps"][1]["tool"] == "gmail.send"


def test_apply_modification_update_parameters():
    wf = sample_canonical_workflow()
    mod = {
        "operation": "UPDATE_PARAMETERS",
        "step_id": "step_slack",
        "parameters": {
            "channel": "#alerts",
        },
    }
    result = apply_modification(wf, mod)
    assert len(result["steps"]) == 2
    assert result["steps"][1]["parameters"]["channel"] == "#alerts"
    assert result["steps"][1]["parameters"]["message"] == "New ticket created"


# -------------------------------------------------------------------------
# Test Cases 12-16: Modification Error Handling & Validation
# -------------------------------------------------------------------------

def test_add_step_duplicate_id_fails():
    wf = sample_canonical_workflow()
    mod = {
        "operation": "ADD_STEP",
        "step": {
            "id": "step_crm",  # already exists
            "tool": "gmail.send",
            "parameters": {"to": "test@example.com", "subject": "Hi", "body": "Hello"},
        },
    }
    with pytest.raises(InvalidModificationError) as exc_info:
        apply_modification(wf, mod)
    assert "already exists" in str(exc_info.value)


def test_remove_step_non_existent_fails():
    wf = sample_canonical_workflow()
    mod = {
        "operation": "REMOVE_STEP",
        "step_id": "non_existent_step",
    }
    with pytest.raises(InvalidModificationError) as exc_info:
        apply_modification(wf, mod)
    assert "not found" in str(exc_info.value)


def test_remove_all_steps_fails():
    wf = sample_canonical_workflow()
    wf["steps"] = [wf["steps"][0]]  # only 1 step left
    mod = {
        "operation": "REMOVE_STEP",
        "step_id": "step_crm",
    }
    with pytest.raises(InvalidModificationError) as exc_info:
        apply_modification(wf, mod)
    assert "at least one step" in str(exc_info.value)


def test_validation_rejects_unknown_tool_before_n8n(tmp_path):
    manager, client, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow")
    auto_mgr = AutomationManager(manager)

    invalid_mod = {
        "operation": "ADD_STEP",
        "step": {
            "id": "step_bad",
            "tool": "unknown.tool",
            "parameters": {},
        },
    }
    modified_wf = apply_modification(sample_canonical_workflow(), invalid_mod)

    with pytest.raises(AutomationCreationError) as exc_info:
        auto_mgr.update_automation("org-a", "auto_123", modified_wf)

    assert exc_info.value.code == "UNKNOWN_TOOL"
    client.update_workflow.assert_not_called()


def test_validation_rejects_missing_parameters_before_n8n(tmp_path):
    manager, client, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow")
    auto_mgr = AutomationManager(manager)

    invalid_mod = {
        "operation": "UPDATE_PARAMETERS",
        "step_id": "step_crm",
        "parameters": {
            "title": "",  # invalid: title must have minLength 1
        },
    }
    # Note: crm.create_ticket requires customer_id, title, priority
    modified_wf = sample_canonical_workflow()
    modified_wf["steps"][0]["parameters"] = {}  # missing required fields

    with pytest.raises(AutomationCreationError) as exc_info:
        auto_mgr.update_automation("org-a", "auto_123", modified_wf)

    assert exc_info.value.code == "INVALID_PARAMETER"
    client.update_workflow.assert_not_called()


def test_preflight_fails_when_integration_disconnected(tmp_path):
    store = IntegrationStateStore(tmp_path / "state.sqlite3")
    manager = IntegrationManager(state_store=store)
    # Only connect CRM, leave Slack disconnected
    manager.connect("org-a", "crm", "FAKE_CRM_SECRET")
    client = MagicMock()
    manager.n8n_client = client

    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow")
    auto_mgr = AutomationManager(manager)

    # Workflow has slack.send_message
    wf = sample_canonical_workflow()

    with pytest.raises(AutomationCreationError) as exc_info:
        auto_mgr.update_automation("org-a", "auto_123", wf)

    assert exc_info.value.code == "MISSING_INTEGRATION"
    client.update_workflow.assert_not_called()


# -------------------------------------------------------------------------
# Test Cases 17-22: Confirmation Flow, Gating, Resume, and Identity
# -------------------------------------------------------------------------

def modify_plan(target="Customer Support Workflow", op="UPDATE_PARAMETERS", step_id="step_slack", params=None):
    return {
        "mode": "AUTOMATE",
        "goal": "Update Slack notification channel",
        "operation": "MODIFY",
        "target_automation": target,
        "modification": {
            "operation": op,
            "step_id": step_id,
            "parameters": params or {"channel": "#urgent-support"},
        },
    }


def test_agent_modify_requires_confirmation_gate(tmp_path):
    manager, client, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow")
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=modify_plan()):
        response = agent.run("Change the Slack channel to #urgent-support", context, ["crm.write", "slack.send"])

    assert response.mode == "AUTOMATE"
    assert response.status == "awaiting_confirmation"
    assert "Customer Support Workflow" in response.response_text
    assert "UPDATE_PARAMETERS" in response.response_text
    client.update_workflow.assert_not_called()


def test_agent_modify_rejection_cancels_without_n8n_call(tmp_path):
    manager, client, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow")
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=modify_plan()):
        agent.run("Change the Slack channel to #urgent-support", context, ["crm.write", "slack.send"])
        rejected = agent.resume_confirmation(context, approved=False)

    assert rejected.status == "cancelled"
    assert rejected.error_code == "CONFIRMATION_REJECTED"
    client.update_workflow.assert_not_called()

    # Verify store was NOT modified
    saved = store.get_automation("org-a", "auto_123")
    assert saved["canonical_workflow"]["steps"][1]["parameters"]["channel"] == "#support"


def test_agent_modify_approval_updates_n8n_and_persistence(tmp_path):
    manager, client, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow", "n8n-wf-100")
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=modify_plan()):
        pending = agent.run("Change the Slack channel", context, ["crm.write", "slack.send"])
        assert pending.status == "awaiting_confirmation"
        approved = agent.resume_confirmation(context, approved=True)

    assert approved.status == "completed"
    assert "Customer Support Workflow" in approved.response_text
    assert "n8n Workflow ID: n8n-wf-100" in approved.response_text

    # Verify n8n client update_workflow was called with n8n workflow ID
    client.update_workflow.assert_called_once()
    n8n_id_arg, payload_arg = client.update_workflow.call_args.args
    assert n8n_id_arg == "n8n-wf-100"
    assert "active" not in payload_arg
    assert "credential_references" not in payload_arg

    # Verify persistence: preserved IDs, updated canonical workflow
    saved = store.get_automation("org-a", "auto_123")
    assert saved["id"] == "auto_123"
    assert saved["n8n_workflow_id"] == "n8n-wf-100"
    assert saved["status"] == "updated"
    assert saved["created_at"] == "2026-01-01T00:00:00Z"
    assert saved["canonical_workflow"]["steps"][1]["parameters"]["channel"] == "#urgent-support"


def test_agent_modify_duplicate_execution_prevented(tmp_path):
    manager, client, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow")
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=modify_plan()):
        agent.run("Change Slack channel", context, ["crm.write", "slack.send"])
        first_approval = agent.resume_confirmation(context, approved=True)
        second_approval = agent.resume_confirmation(context, approved=True)

    assert first_approval.status == "completed"
    assert second_approval.response_text.startswith("No pending actions")
    client.update_workflow.assert_called_once()


def test_agent_modify_cannot_be_overwritten_by_new_run_while_pending(tmp_path):
    manager, client, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow")
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    with patch("backend.agent.agent.plan", return_value=modify_plan()) as planner:
        first = agent.run("Change Slack channel", context, ["crm.write", "slack.send"])
        second = agent.run("Do something else", context, ["crm.write", "slack.send"])

    assert first.status == "awaiting_confirmation"
    assert second.status == "awaiting_confirmation"
    assert second.error_code == "CONFIRMATION_REQUIRED"
    assert planner.call_count == 1
    client.update_workflow.assert_not_called()


def test_unauthorized_tool_modification_rejected(tmp_path):
    """Test 1: Introducing an unauthorized tool (e.g. gmail.send) is rejected before confirmation."""
    manager, client, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow")
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    # Modification introduces gmail.send
    plan_with_gmail = {
        "mode": "AUTOMATE",
        "goal": "Add Gmail notification to workflow",
        "operation": "MODIFY",
        "target_automation": "Customer Support Workflow",
        "modification": {
            "operation": "ADD_STEP",
            "step": {
                "id": "step_gmail",
                "tool": "gmail.send",
                "parameters": {"to": "ops@example.com", "subject": "Alert", "body": "Details"},
            },
        },
    }

    # User only holds permissions for CRM and Slack, lacks gmail.send
    with patch("backend.agent.agent.plan", return_value=plan_with_gmail):
        result = agent.run("Add Gmail notification", context, ["crm.write", "slack.send"])

    # Assert rejection
    assert result.status == "blocked"
    assert result.error_code == "PERMISSION_DENIED"
    assert "gmail.send" in result.error
    assert len(context.pending_steps) == 0
    assert context.pending_plan is None
    assert context.pending_mode is None
    assert context.pending_automation_id is None
    assert context.pending_automation_workflow is None

    # Assert no n8n update and no persistence update
    client.update_workflow.assert_not_called()
    saved = store.get_automation("org-a", "auto_123")
    assert len(saved["canonical_workflow"]["steps"]) == 2  # still original 2 steps


def test_authorized_modification_reaches_confirmation_and_updates(tmp_path):
    """Test 2: When user has all required permissions, modification proceeds through confirmation."""
    manager, client, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow")
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    plan_with_gmail = {
        "mode": "AUTOMATE",
        "goal": "Add Gmail notification to workflow",
        "operation": "MODIFY",
        "target_automation": "Customer Support Workflow",
        "modification": {
            "operation": "ADD_STEP",
            "step": {
                "id": "step_gmail",
                "tool": "gmail.send",
                "parameters": {"to": "ops@example.com", "subject": "Alert", "body": "Details"},
            },
        },
    }

    # User holds ALL required permissions including gmail.send
    with patch("backend.agent.agent.plan", return_value=plan_with_gmail):
        pending = agent.run("Add Gmail notification", context, ["crm.write", "slack.send", "gmail.send"])

    assert pending.status == "awaiting_confirmation"
    assert pending.mode == "AUTOMATE"
    client.update_workflow.assert_not_called()

    # Now approve and verify completion
    approved = agent.resume_confirmation(context, approved=True)
    assert approved.status == "completed"
    client.update_workflow.assert_called_once()
    saved = store.get_automation("org-a", "auto_123")
    assert len(saved["canonical_workflow"]["steps"]) == 3
    assert saved["canonical_workflow"]["steps"][2]["tool"] == "gmail.send"


def test_mixed_workflow_permission_enforcement(tmp_path):
    """Test 3: Checks all tools in resulting workflow, rejecting if user lacks permission for existing tool."""
    manager, client, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow")
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    # Modification adds gmail.send
    plan_with_gmail = {
        "mode": "AUTOMATE",
        "goal": "Add Gmail notification",
        "operation": "MODIFY",
        "target_automation": "Customer Support Workflow",
        "modification": {
            "operation": "ADD_STEP",
            "step": {
                "id": "step_gmail",
                "tool": "gmail.send",
                "parameters": {"to": "ops@example.com", "subject": "Alert", "body": "Details"},
            },
        },
    }

    # User has permission for gmail.send, but lacks slack.send which is in the resulting workflow!
    with patch("backend.agent.agent.plan", return_value=plan_with_gmail):
        result = agent.run("Add Gmail step", context, ["crm.write", "gmail.send"])  # missing slack.send

    assert result.status == "blocked"
    assert result.error_code == "PERMISSION_DENIED"
    assert "slack.send" in result.error
    assert len(context.pending_steps) == 0
    client.update_workflow.assert_not_called()



def test_agent_modify_target_not_found_returns_error(tmp_path):
    manager, client, store = configured_manager(tmp_path)
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    plan_unknown = modify_plan(target="Nonexistent Workflow")
    with patch("backend.agent.agent.plan", return_value=plan_unknown):
        result = agent.run("Modify nonexistent workflow", context, ["slack.send"])

    assert result.status == "error"
    assert result.error_code == "AUTOMATION_NOT_FOUND"
    client.update_workflow.assert_not_called()


def test_agent_modify_target_ambiguous_returns_error(tmp_path):
    manager, client, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_1", "Support Workflow A")
    seed_automation(store, "org-a", "auto_2", "Support Workflow B")
    agent = Agent(manager)
    context = ConversationContext("user-a", "org-a", integration_manager=manager)

    plan_ambiguous = modify_plan(target="Support Workflow")
    with patch("backend.agent.agent.plan", return_value=plan_ambiguous):
        result = agent.run("Modify support workflow", context, ["slack.send"])

    assert result.status == "error"
    assert result.error_code == "AUTOMATION_AMBIGUOUS"
    client.update_workflow.assert_not_called()


# -------------------------------------------------------------------------
# Test Cases 23-24: Structural Validation and Secret Safety
# -------------------------------------------------------------------------

def test_planner_structure_validation_for_modify():
    valid_modify = {
        "mode": "AUTOMATE",
        "goal": "Modify workflow",
        "operation": "MODIFY",
        "target_automation": "auto_123",
        "modification": {"operation": "REMOVE_STEP", "step_id": "step_slack"},
    }
    _validate_plan_structure(valid_modify)
    assert valid_modify["steps"] == []

    # Missing target_automation
    invalid_no_target = {
        "mode": "AUTOMATE",
        "goal": "Modify workflow",
        "operation": "MODIFY",
        "modification": {"operation": "REMOVE_STEP", "step_id": "step_slack"},
    }
    with pytest.raises(ValueError, match="target_automation"):
        _validate_plan_structure(invalid_no_target)

    # Missing modification
    invalid_no_mod = {
        "mode": "AUTOMATE",
        "goal": "Modify workflow",
        "operation": "MODIFY",
        "target_automation": "auto_123",
    }
    with pytest.raises(ValueError, match="modification object"):
        _validate_plan_structure(invalid_no_mod)


def test_agent_plan_validator_for_modify():
    valid_plan = {
        "mode": "AUTOMATE",
        "goal": "Update automation",
        "operation": "MODIFY",
        "target_automation": "auto_123",
        "modification": {"operation": "UPDATE_PARAMETERS", "step_id": "step_1", "parameters": {}},
    }
    validated = validate_agent_plan(valid_plan)
    assert validated == valid_plan

    # Missing goal
    with pytest.raises(ValidationError):
        validate_agent_plan({**valid_plan, "goal": ""})


def test_credential_safety_in_modified_payload(tmp_path):
    manager, client, store = configured_manager(tmp_path)
    seed_automation(store, "org-a", "auto_123", "Customer Support Workflow", "n8n-wf-100")
    auto_mgr = AutomationManager(manager)

    mod = {
        "operation": "ADD_STEP",
        "step": {
            "id": "step_gmail",
            "tool": "gmail.send",
            "parameters": {"to": "audit@example.com", "subject": "Notice", "body": "Audit log"},
        },
    }
    modified_wf = apply_modification(sample_canonical_workflow(), mod)
    auto_mgr.update_automation("org-a", "auto_123", modified_wf)

    # Check payload sent to n8n client
    client.update_workflow.assert_called_once()
    payload = client.update_workflow.call_args.args[1]
    payload_str = str(payload)

    assert "FAKE_CRM_SECRET" not in payload_str
    assert "FAKE_SLACK_SECRET" not in payload_str
    assert "FAKE_GMAIL_SECRET" not in payload_str


def test_live_n8n_workflow_modification(tmp_path):
    """Safe live test against running n8n instance if available."""
    try:
        import dotenv
        import os
        dotenv.load_dotenv()
        base_url = os.environ.get("N8N_BASE_URL", "http://localhost:5678")
        api_key = os.environ.get("N8N_API_KEY", "")
        if not api_key:
            pytest.skip("N8N_API_KEY not configured for live test")
        client = N8nClient(N8nConfig(base_url, api_key, timeout=5.0))
        health = client.health_check()
        if health.get("status") != "ok":
            pytest.skip("n8n health check not ok")
    except Exception:
        pytest.skip("n8n instance not reachable in current execution mode")

    store = IntegrationStateStore(tmp_path / "live_state.sqlite3")
    mgr = IntegrationManager(state_store=store)
    conn = mgr.connect("live-test-org", "crm", "fake-crm-key")
    mgr.n8n_credential_provider.register_mapping(
        "live-test-org", conn.credential_reference, "n8n-crm-1", "crm"
    )
    mgr.n8n_client = client

    auto_mgr = AutomationManager(mgr, n8n_client=client)
    canonical = {
        "mode": "AUTOMATE",
        "name": "Live Phase 8 Test Automation",
        "trigger": {"type": "webhook", "parameters": {"path": "live-p8-test"}},
        "steps": [
            {
                "id": "step_1",
                "tool": "crm.find_order",
                "parameters": {"order_id": "100"},
            }
        ],
    }

    created = auto_mgr.create_automation("live-test-org", canonical)
    n8n_id = created["n8n_workflow_id"]
    auto_id = created["automation_id"]

    try:
        mod = {
            "operation": "UPDATE_PARAMETERS",
            "step_id": "step_1",
            "parameters": {"order_id": "200"},
        }
        modified_wf = auto_mgr.apply_modification(canonical, mod)
        updated = auto_mgr.update_automation("live-test-org", auto_id, modified_wf)

        assert updated["status"] == "updated"
        assert updated["n8n_workflow_id"] == n8n_id
        assert updated["automation_id"] == auto_id

        # Verify against live n8n API
        live_wf = client.get_workflow(n8n_id)
        assert live_wf.get("name") == "Live Phase 8 Test Automation"
        assert len(live_wf.get("nodes", [])) == 2
    finally:
        try:
            client.delete_workflow(n8n_id)
        except Exception:
            pass
