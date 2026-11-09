"""Comprehensive tests for Phase 11 FastAPI backend layer."""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.dependencies import clear_session_contexts, set_state_store
from backend.integrations.persistence import IntegrationStateStore


@pytest.fixture
def test_store(tmp_path):
    """Isolated state store fixture for FastAPI tests."""
    store = IntegrationStateStore(tmp_path / "api_test.sqlite3")
    set_state_store(store)
    clear_session_contexts()
    yield store
    clear_session_contexts()
    set_state_store(None)


@pytest.fixture
def client(test_store):
    return TestClient(app)


# ─── 1. STARTUP & ROUTE REGISTRATION ─────────────────────────────────────────

def test_api_startup_and_healthz(client):
    res = client.get("/api/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "voice2flow-api"}


# ─── 2. TENANT CONTEXT HEADERS ────────────────────────────────────────────────

def test_missing_tenant_headers_rejected(client):
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 400
    assert "Missing required header" in res.json()["error"]

    res = client.get(
        "/api/dashboard/stats",
        headers={"X-Organization-Id": "org-1"},
    )
    assert res.status_code == 400
    assert "Missing required header 'X-User-Id'" in res.json()["error"]


def test_valid_tenant_headers_accepted(client):
    headers = {
        "X-Organization-Id": "org-test-1",
        "X-User-Id": "user-test-1",
        "X-User-Permissions": "crm.read,slack.send",
    }
    res = client.get("/api/dashboard/stats", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "automations" in data
    assert "integrations" in data


# ─── 3. AGENT CHAT & MODES ────────────────────────────────────────────────────

def test_agent_chat_ask_mode(client):
    headers = {
        "X-Organization-Id": "org-ask",
        "X-User-Id": "user-ask",
        "X-User-Permissions": "crm.read",
    }
    mock_plan = {
        "mode": "ASK",
        "goal": "Count delayed orders",
        "steps": [{"id": "step_1", "tool": "crm.find_order", "parameters": {"status": "delayed"}}],
    }

    with patch("backend.agent.agent.plan", return_value=mock_plan):
        res = client.post(
            "/api/agent/chat",
            json={"message": "How many delayed orders?", "dry_run": True},
            headers=headers,
        )

    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "ASK"
    assert data["status"] == "completed"
    assert data["conversation_id"].startswith("conv_")
    assert data["run_id"] is not None
    assert data["pending_confirmation"] is None


def test_agent_chat_awaiting_confirmation_mode(client):
    headers = {
        "X-Organization-Id": "org-do",
        "X-User-Id": "user-do",
        "X-User-Permissions": "slack.send",
    }
    mock_plan = {
        "mode": "DO",
        "goal": "Send alert to slack",
        "steps": [{"id": "step_1", "tool": "slack.send_message", "parameters": {"channel": "#alerts", "message": "Hi"}}],
    }

    with patch("backend.agent.agent.plan", return_value=mock_plan):
        res = client.post(
            "/api/agent/chat",
            json={"message": "Send alert to slack"},
            headers=headers,
        )

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "awaiting_confirmation"
    assert data["pending_confirmation"] is not None
    assert data["pending_confirmation"]["risk"] == "medium"
    assert len(data["pending_confirmation"]["steps"]) == 1


# ─── 4. CONFIRMATION FLOW & CROSS-TENANT ISOLATION ────────────────────────────

def test_confirmation_approval_lifecycle(client):
    headers = {
        "X-Organization-Id": "org-flow",
        "X-User-Id": "user-flow",
        "X-User-Permissions": "slack.send",
    }
    mock_plan = {
        "mode": "DO",
        "goal": "Send Slack update",
        "steps": [{"id": "step_1", "tool": "slack.send_message", "parameters": {"channel": "#updates", "message": "Deploy done"}}],
    }

    with patch("backend.agent.agent.plan", return_value=mock_plan):
        init_res = client.post(
            "/api/agent/chat",
            json={"message": "Post to slack"},
            headers=headers,
        )

    assert init_res.status_code == 200
    chat_data = init_res.json()
    assert chat_data["status"] == "awaiting_confirmation"
    conv_id = chat_data["conversation_id"]
    run_id = chat_data["run_id"]

    # Approve with dry_run
    confirm_res = client.post(
        "/api/agent/confirm",
        json={"run_id": run_id, "conversation_id": conv_id, "approved": True, "dry_run": True},
        headers=headers,
    )
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["status"] == "completed"

    # Replay attempt must fail (already completed / no pending action)
    replay_res = client.post(
        "/api/agent/confirm",
        json={"run_id": run_id, "conversation_id": conv_id, "approved": True},
        headers=headers,
    )
    assert replay_res.status_code == 404


def test_confirmation_rejection_cancels_action(client):
    headers = {
        "X-Organization-Id": "org-reject",
        "X-User-Id": "user-reject",
        "X-User-Permissions": "slack.send",
    }
    mock_plan = {
        "mode": "DO",
        "goal": "Send message",
        "steps": [{"id": "step_1", "tool": "slack.send_message", "parameters": {"channel": "#alerts", "message": "Alert"}}],
    }

    with patch("backend.agent.agent.plan", return_value=mock_plan):
        init_res = client.post("/api/agent/chat", json={"message": "Send alert"}, headers=headers)
    data = init_res.json()

    reject_res = client.post(
        "/api/agent/confirm",
        json={"run_id": data["run_id"], "conversation_id": data["conversation_id"], "approved": False},
        headers=headers,
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "cancelled"


def test_cross_tenant_cannot_confirm_other_tenant_action(client):
    tenant_a_headers = {
        "X-Organization-Id": "org-tenant-a",
        "X-User-Id": "user-a",
        "X-User-Permissions": "slack.send",
    }
    tenant_b_headers = {
        "X-Organization-Id": "org-tenant-b",
        "X-User-Id": "user-b",
        "X-User-Permissions": "slack.send",
    }

    mock_plan = {
        "mode": "DO",
        "goal": "Org A action",
        "steps": [{"id": "step_1", "tool": "slack.send_message", "parameters": {"channel": "#a", "message": "test"}}],
    }

    with patch("backend.agent.agent.plan", return_value=mock_plan):
        init_res = client.post("/api/agent/chat", json={"message": "Send"}, headers=tenant_a_headers)
    data = init_res.json()
    conv_id = data["conversation_id"]
    run_id = data["run_id"]

    # Tenant B attempts to approve Tenant A's pending action
    bad_res = client.post(
        "/api/agent/confirm",
        json={"run_id": run_id, "conversation_id": conv_id, "approved": True},
        headers=tenant_b_headers,
    )
    assert bad_res.status_code == 404
    assert "No pending operation found" in bad_res.json()["error"]


# ─── 5. AUTOMATIONS TENANT ISOLATION ──────────────────────────────────────────

def test_automations_tenant_isolation(client, test_store):
    # Seed automation for Org A
    auto_a = {
        "id": "auto_org_a",
        "organization_id": "org-a",
        "n8n_workflow_id": "wf_a",
        "name": "Org A Workflow",
        "status": "created",
        "canonical_workflow": {"name": "Org A Workflow", "steps": [{"tool": "crm.find_order"}]},
        "created_at": "2026-11-09T00:00:00Z",
        "updated_at": "2026-11-09T00:00:00Z",
    }
    test_store.save_automation(auto_a)

    headers_a = {"X-Organization-Id": "org-a", "X-User-Id": "user-a"}
    headers_b = {"X-Organization-Id": "org-b", "X-User-Id": "user-b"}

    # Org A sees it
    res_a = client.get("/api/automations", headers=headers_a)
    assert res_a.status_code == 200
    assert len(res_a.json()) == 1
    assert res_a.json()[0]["id"] == "auto_org_a"

    # Org B does not see it
    res_b = client.get("/api/automations", headers=headers_b)
    assert res_b.status_code == 200
    assert len(res_b.json()) == 0

    # Org B cannot get by ID
    res_b_detail = client.get("/api/automations/auto_org_a", headers=headers_b)
    assert res_b_detail.status_code == 404


# ─── 6. INTEGRATIONS & SECRET REDACTION ───────────────────────────────────────

def test_integrations_list_and_connect_never_exposes_secrets(client):
    headers = {"X-Organization-Id": "org-integ", "X-User-Id": "user-integ"}

    # List initial
    list_res = client.get("/api/integrations", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(i["integration"] == "crm" for i in items)

    # Connect CRM
    conn_res = client.post(
        "/api/integrations/crm/connect",
        json={"secret": "TOP_SECRET_CRM_KEY_12345", "account_identifier": "sales@gnani.ai"},
        headers=headers,
    )
    assert conn_res.status_code == 200
    conn_data = conn_res.json()
    assert conn_data["status"] == "connected"
    assert "TOP_SECRET_CRM_KEY_12345" not in str(conn_data)

    # Verify list shows connected without secret
    updated_res = client.get("/api/integrations", headers=headers)
    crm_item = next(i for i in updated_res.json() if i["integration"] == "crm")
    assert crm_item["status"] == "connected"
    assert crm_item["account_identifier"] == "sales@gnani.ai"
    assert "TOP_SECRET" not in str(updated_res.json())

    # Disconnect
    disc_res = client.post("/api/integrations/crm/disconnect", headers=headers)
    assert disc_res.status_code == 200
    assert disc_res.json()["status"] == "disconnected"


# ─── 7. ACTIVITY & EXECUTIONS API ─────────────────────────────────────────────

def test_activity_and_executions_endpoints(client, test_store):
    headers_a = {"X-Organization-Id": "org-audit-a", "X-User-Id": "user-a"}
    headers_b = {"X-Organization-Id": "org-audit-b", "X-User-Id": "user-b"}

    test_store.save_audit_event("org-audit-a", "PLAN_CREATED", run_id="run-1", metadata={"password": "SECRET_PASS"})
    test_store.save_execution({"organization_id": "org-audit-a", "mode": "DO", "status": "completed"})

    # Org A sees audit & execution
    act_a = client.get("/api/activity", headers=headers_a)
    assert act_a.status_code == 200
    assert len(act_a.json()) == 1
    assert "SECRET_PASS" not in str(act_a.json())

    exec_a = client.get("/api/executions", headers=headers_a)
    assert exec_a.status_code == 200
    assert len(exec_a.json()) == 1

    # Org B sees nothing
    act_b = client.get("/api/activity", headers=headers_b)
    assert act_b.status_code == 200
    assert len(act_b.json()) == 0

    exec_b = client.get("/api/executions", headers=headers_b)
    assert exec_b.status_code == 200
    assert len(exec_b.json()) == 0


# ─── 8. PHASE 11D — AGENT UI INTEGRATION FLOWS ────────────────────────────────

def test_phase11d_ask_flow(client):
    headers = {
        "X-Organization-Id": "org-ui-ask",
        "X-User-Id": "user-ui-ask",
        "X-User-Permissions": "crm.read",
    }
    mock_plan = {
        "mode": "ASK",
        "goal": "Find customer John",
        "steps": [{"id": "step_1", "tool": "crm.find_customer", "parameters": {"query": "John"}}],
    }

    with patch("backend.agent.agent.plan", return_value=mock_plan):
        res = client.post(
            "/api/agent/chat",
            json={"message": "Find customer John", "dry_run": True},
            headers=headers,
        )

    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "ASK"
    assert data["status"] == "completed"
    assert data["conversation_id"].startswith("conv_")
    assert data["run_id"] is not None
    assert data["pending_confirmation"] is None
    assert len(data["response"]) > 0


def test_phase11d_do_confirmation_flow(client):
    headers = {
        "X-Organization-Id": "org-ui-do",
        "X-User-Id": "user-ui-do",
        "X-User-Permissions": "slack.send",
    }
    mock_plan = {
        "mode": "DO",
        "goal": "Send Slack message to support",
        "steps": [{"id": "step_1", "tool": "slack.send_message", "parameters": {"channel": "#support", "message": "Urgent update"}}],
    }

    with patch("backend.agent.agent.plan", return_value=mock_plan):
        chat_res = client.post(
            "/api/agent/chat",
            json={"message": "Send a Slack message to the support team"},
            headers=headers,
        )

    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["status"] == "awaiting_confirmation"
    assert chat_data["pending_confirmation"] is not None
    assert chat_data["pending_confirmation"]["risk"] in ["low", "medium", "high"]
    conv_id = chat_data["conversation_id"]
    run_id = chat_data["run_id"]

    # Confirm with approval
    confirm_res = client.post(
        "/api/agent/confirm",
        json={"run_id": run_id, "conversation_id": conv_id, "approved": True, "dry_run": True},
        headers=headers,
    )
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["status"] == "completed"
    assert confirm_data["conversation_id"] == conv_id


def test_phase11d_automate_flow(client):
    headers = {
        "X-Organization-Id": "org-ui-auto",
        "X-User-Id": "user-ui-auto",
        "X-User-Permissions": "crm.read,crm.write,slack.send",
    }

    # Pre-connect required integrations via API
    client.post("/api/integrations/crm/connect", json={"secret": "crm_key_123"}, headers=headers)
    client.post("/api/integrations/slack/connect", json={"secret": "slack_key_123"}, headers=headers)

    mock_plan = {
        "mode": "AUTOMATE",
        "goal": "Create complaint automation",
        "operation": "CREATE",
        "automation_config": {
            "trigger_type": "webhook",
            "trigger_config": {"path": "complaints"},
            "name": "Website Complaints Workflow",
        },
        "steps": [{"id": "step_1", "tool": "slack.send_message", "parameters": {"channel": "complaints", "message": "New complaint"}}],
    }

    mock_auto_result = {
        "status": "created",
        "automation_id": "auto_ui_test_123",
        "n8n_workflow_id": "n8n_wf_ui_123",
        "workflow_name": "Website Complaints Workflow",
        "message": "Automation created successfully.",
    }

    with patch("backend.agent.agent.plan", return_value=mock_plan):
        with patch("backend.agent.automation_manager.AutomationManager.create_automation", return_value=mock_auto_result):
            chat_res = client.post(
                "/api/agent/chat",
                json={"message": "Create an automation for new website complaints"},
                headers=headers,
            )

            assert chat_res.status_code == 200
            chat_data = chat_res.json()
            assert chat_data["status"] == "awaiting_confirmation"
            conv_id = chat_data["conversation_id"]
            run_id = chat_data["run_id"]

            confirm_res = client.post(
                "/api/agent/confirm",
                json={"run_id": run_id, "conversation_id": conv_id, "approved": True},
                headers=headers,
            )
            assert confirm_res.status_code == 200
            confirm_data = confirm_res.json()
            assert confirm_data["status"] == "completed"
            auto_result = confirm_data["execution_results"]["automation"]
            assert auto_result["automation_id"] == "auto_ui_test_123"
            assert auto_result["n8n_workflow_id"] == "n8n_wf_ui_123"


def test_phase11d_reject_flow(client):
    headers = {
        "X-Organization-Id": "org-ui-rej",
        "X-User-Id": "user-ui-rej",
        "X-User-Permissions": "slack.send",
    }
    mock_plan = {
        "mode": "DO",
        "goal": "Send alert",
        "steps": [{"id": "step_1", "tool": "slack.send_message", "parameters": {"channel": "#alerts", "message": "Alert"}}],
    }

    with patch("backend.agent.agent.plan", return_value=mock_plan):
        chat_res = client.post(
            "/api/agent/chat",
            json={"message": "Send alert to channel"},
            headers=headers,
        )

    assert chat_res.status_code == 200
    conv_id = chat_res.json()["conversation_id"]
    run_id = chat_res.json()["run_id"]

    # Reject
    reject_res = client.post(
        "/api/agent/confirm",
        json={"run_id": run_id, "conversation_id": conv_id, "approved": False},
        headers=headers,
    )
    assert reject_res.status_code == 200
    reject_data = reject_res.json()
    assert reject_data["status"] == "cancelled"
    assert "cancel" in reject_data["response"].lower() or "reject" in reject_data["response"].lower()

    # Replay is rejected (404)
    replay_res = client.post(
        "/api/agent/confirm",
        json={"run_id": run_id, "conversation_id": conv_id, "approved": True},
        headers=headers,
    )
    assert replay_res.status_code == 404


def test_phase11d_conversation_continuity(client):
    headers = {
        "X-Organization-Id": "org-ui-cont",
        "X-User-Id": "user-ui-cont",
        "X-User-Permissions": "crm.read",
    }
    mock_plan_1 = {
        "mode": "ASK",
        "goal": "Find customer John",
        "steps": [{"id": "s1", "tool": "crm.find_customer", "parameters": {"name": "John"}}],
    }
    mock_plan_2 = {
        "mode": "ASK",
        "goal": "Find recent orders",
        "steps": [{"id": "s2", "tool": "crm.find_order", "parameters": {"customer": "John"}}],
    }

    with patch("backend.agent.agent.plan", return_value=mock_plan_1):
        res1 = client.post(
            "/api/agent/chat",
            json={"message": "Find customer John", "dry_run": True},
            headers=headers,
        )
    assert res1.status_code == 200
    conv_id = res1.json()["conversation_id"]

    # Subsequent message passes the same conversation_id
    with patch("backend.agent.agent.plan", return_value=mock_plan_2):
        res2 = client.post(
            "/api/agent/chat",
            json={"message": "Find his recent orders", "conversation_id": conv_id, "dry_run": True},
            headers=headers,
        )
    assert res2.status_code == 200
    assert res2.json()["conversation_id"] == conv_id


def test_phase11d_tenant_contract_adherence(client):
    # Reject X-Tenant-ID header when missing X-Organization-Id
    res = client.post(
        "/api/agent/chat",
        json={"message": "Test message"},
        headers={"X-Tenant-ID": "tenant-1", "X-User-Id": "user-1"},
    )
    assert res.status_code == 400
    assert "Missing required header 'X-Organization-Id'" in res.json()["error"]


# ─── 9. PHASE 11E — AUTOMATION MANAGEMENT API FLOWS ───────────────────────────

def test_phase11e_automations_list_and_detail_flow(client, test_store):
    headers = {
        "X-Organization-Id": "org-ui-auto-mgmt",
        "X-User-Id": "user-auto-mgmt",
    }

    # Seed automation with canonical workflow containing trigger and steps
    auto_record = {
        "id": "auto_complaint_flow_123",
        "organization_id": "org-ui-auto-mgmt",
        "n8n_workflow_id": "n8n_wf_789",
        "name": "Customer Complaint Handler",
        "status": "created",
        "canonical_workflow": {
            "name": "Customer Complaint Handler",
            "trigger": {
                "type": "webhook",
                "parameters": {"path": "complaints"},
            },
            "steps": [
                {
                    "id": "create_ticket",
                    "tool": "crm.create_ticket",
                    "parameters": {
                        "customer_id": "{{trigger.customer_id}}",
                        "title": "Customer complaint",
                    },
                },
                {
                    "id": "notify_support",
                    "tool": "slack.send_message",
                    "parameters": {
                        "channel": "support",
                        "message": "Ticket: {{create_ticket.ticket_id}}",
                    },
                },
            ],
        },
        "created_at": "2026-11-09T08:00:00Z",
        "updated_at": "2026-11-09T08:00:00Z",
    }
    test_store.save_automation(auto_record)

    # 1. Test GET /api/automations (List)
    list_res = client.get("/api/automations", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert len(list_data) == 1
    summary = list_data[0]
    assert summary["id"] == "auto_complaint_flow_123"
    assert summary["name"] == "Customer Complaint Handler"
    assert summary["status"] == "created"
    assert summary["step_count"] == 2
    assert summary["n8n_workflow_id"] == "n8n_wf_789"

    # 2. Test GET /api/automations/{id} (Detail)
    detail_res = client.get("/api/automations/auto_complaint_flow_123", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == "auto_complaint_flow_123"
    assert detail["organization_id"] == "org-ui-auto-mgmt"
    assert detail["name"] == "Customer Complaint Handler"
    wf = detail["canonical_workflow"]
    assert wf["trigger"]["type"] == "webhook"
    assert len(wf["steps"]) == 2
    assert wf["steps"][0]["tool"] == "crm.create_ticket"
    assert wf["steps"][1]["tool"] == "slack.send_message"


def test_phase11e_automation_not_found(client):
    headers = {
        "X-Organization-Id": "org-ui-auto-mgmt",
        "X-User-Id": "user-auto-mgmt",
    }
    res = client.get("/api/automations/non_existent_auto_999", headers=headers)
    assert res.status_code == 404
    assert "Automation 'non_existent_auto_999' not found." in res.json()["error"]


def test_phase11e_automations_header_validation(client):
    res = client.get("/api/automations", headers={"X-Tenant-ID": "org-bad", "X-User-Id": "user-1"})
    assert res.status_code == 400
    assert "Missing required header 'X-Organization-Id'" in res.json()["error"]


# ─── 10. PHASE 11F — INTEGRATION MANAGEMENT API FLOWS ─────────────────────────

def test_phase11f_integrations_list(client):
    headers = {
        "X-Organization-Id": "org-ui-integrations",
        "X-User-Id": "user-integrations",
    }
    res = client.get("/api/integrations", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 3  # gmail, slack, crm

    keys = {item["integration"] for item in data}
    assert "gmail" in keys
    assert "slack" in keys
    assert "crm" in keys

    for item in data:
        assert "name" in item
        assert "status" in item
        assert item["status"] in ("connected", "disconnected")
        assert "account_identifier" in item
        assert "connected_at" in item


def test_phase11f_connect_and_disconnect_lifecycle(client):
    headers = {
        "X-Organization-Id": "org-ui-lifecycle",
        "X-User-Id": "user-lifecycle",
    }

    # 1. Initially disconnected
    res = client.get("/api/integrations", headers=headers)
    assert res.status_code == 200
    slack_entry = next(i for i in res.json() if i["integration"] == "slack")
    assert slack_entry["status"] == "disconnected"

    # 2. Connect Slack
    connect_payload = {
        "secret": "xoxb-test-token-123456",
        "account_identifier": "#engineering-alerts",
    }
    connect_res = client.post(
        "/api/integrations/slack/connect",
        json=connect_payload,
        headers=headers,
    )
    assert connect_res.status_code == 200
    conn_data = connect_res.json()
    assert conn_data["status"] == "connected"
    assert conn_data["integration"] == "slack"
    assert conn_data["account_identifier"] == "#engineering-alerts"
    assert "secret" not in conn_data  # Credentials never exposed

    # 3. Verify status updated in list
    res_after = client.get("/api/integrations", headers=headers)
    assert res_after.status_code == 200
    slack_updated = next(i for i in res_after.json() if i["integration"] == "slack")
    assert slack_updated["status"] == "connected"
    assert slack_updated["account_identifier"] == "#engineering-alerts"
    assert slack_updated["connected_at"] is not None

    # 4. Disconnect Slack
    disconnect_res = client.post(
        "/api/integrations/slack/disconnect",
        headers=headers,
    )
    assert disconnect_res.status_code == 200
    disconn_data = disconnect_res.json()
    assert disconn_data["status"] == "disconnected"
    assert disconn_data["integration"] == "slack"

    # 5. Verify status is disconnected again
    res_final = client.get("/api/integrations", headers=headers)
    assert res_final.status_code == 200
    slack_final = next(i for i in res_final.json() if i["integration"] == "slack")
    assert slack_final["status"] == "disconnected"


def test_phase11f_disconnect_not_connected_404(client):
    headers = {
        "X-Organization-Id": "org-ui-notconn",
        "X-User-Id": "user-notconn",
    }
    # Disconnecting an integration that was never connected should return 404
    res = client.post(
        "/api/integrations/gmail/disconnect",
        headers=headers,
    )
    assert res.status_code == 404
    assert "not currently connected" in res.json()["error"]


def test_phase11f_connect_unsupported_400(client):
    headers = {
        "X-Organization-Id": "org-ui-unsupported",
        "X-User-Id": "user-unsupported",
    }
    res = client.post(
        "/api/integrations/nonexistent_service_xyz/connect",
        json={"secret": "invalid-secret"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Failed to connect integration" in res.json()["error"]
    assert "Unsupported integration" in res.json()["error"]


def test_phase11f_integrations_header_validation(client):
    # Missing headers on GET
    res = client.get("/api/integrations")
    assert res.status_code == 400

    # Wrong header (X-Tenant-ID instead of X-Organization-Id)
    res = client.get(
        "/api/integrations",
        headers={"X-Tenant-ID": "tenant-legacy", "X-User-Id": "user-1"},
    )
    assert res.status_code == 400
    assert "Missing required header 'X-Organization-Id'" in res.json()["error"]

    # Missing headers on POST connect
    res = client.post(
        "/api/integrations/slack/connect",
        json={"secret": "test"},
    )
    assert res.status_code == 400


# ─── 11. PHASE 11G — ACTIVITY & EXECUTION OBSERVABILITY FLOWS ─────────────────

def test_phase11g_activity_list_pagination_and_redaction(client, test_store):
    headers = {
        "X-Organization-Id": "org-ui-act",
        "X-User-Id": "user-act",
    }

    # Seed 3 audit events with some sensitive metadata
    test_store.save_audit_event(
        "org-ui-act",
        "AGENT_REQUEST",
        run_id="run-act-1",
        user_id="user-act",
        metadata={"api_key": "raw_secret_key_1", "message_length": 42},
    )
    test_store.save_audit_event(
        "org-ui-act",
        "PLAN_CREATED",
        run_id="run-act-2",
        user_id="user-act",
        mode="DO",
        metadata={"step_count": 2, "client_secret": "my_secret"},
    )
    test_store.save_audit_event(
        "org-ui-act",
        "AUTOMATION_CREATED",
        run_id="run-act-3",
        user_id="user-act",
        metadata={"workflow_name": "Complaint Pipeline"},
    )

    # 1. Test pagination limit=2, offset=0
    res_page1 = client.get("/api/activity?limit=2&offset=0", headers=headers)
    assert res_page1.status_code == 200
    events_p1 = res_page1.json()
    assert len(events_p1) == 2

    # 2. Test pagination limit=2, offset=2
    res_page2 = client.get("/api/activity?limit=2&offset=2", headers=headers)
    assert res_page2.status_code == 200
    events_p2 = res_page2.json()
    assert len(events_p2) == 1

    # 3. Verify sensitive fields were redacted at the persistence boundary
    all_res = client.get("/api/activity?limit=10&offset=0", headers=headers)
    assert all_res.status_code == 200
    all_data_str = str(all_res.json())
    assert "raw_secret_key_1" not in all_data_str
    assert "my_secret" not in all_data_str
    assert "[REDACTED]" in all_data_str


def test_phase11g_executions_list_pagination_and_provenance(client, test_store):
    headers = {
        "X-Organization-Id": "org-ui-exec",
        "X-User-Id": "user-exec",
    }

    # Seed 3 executions: completed, failed, and running
    test_store.save_execution({
        "id": "exec_success_1",
        "organization_id": "org-ui-exec",
        "user_id": "user-exec",
        "automation_id": "auto_sync_999",
        "mode": "DO",
        "status": "completed",
        "started_at": "2026-11-09T08:00:00Z",
        "completed_at": "2026-11-09T08:00:02Z",
        "metadata": {"records_processed": 50},
    })
    test_store.save_execution({
        "id": "exec_failed_1",
        "organization_id": "org-ui-exec",
        "user_id": "user-exec",
        "mode": "AUTOMATE",
        "status": "error",
        "error_code": "AUTOMATION_CREATION_FAILED",
        "started_at": "2026-11-09T08:05:00Z",
        "completed_at": "2026-11-09T08:05:01Z",
        "metadata": {"failure_reason": "Missing trigger path"},
    })
    test_store.save_execution({
        "id": "exec_running_1",
        "organization_id": "org-ui-exec",
        "user_id": "user-exec",
        "mode": "ASK",
        "status": "running",
        "started_at": "2026-11-09T08:10:00Z",
        "metadata": {},
    })

    # Fetch executions list
    res = client.get("/api/executions?limit=10&offset=0", headers=headers)
    assert res.status_code == 200
    records = res.json()
    assert len(records) == 3

    success_rec = next(r for r in records if r["id"] == "exec_success_1")
    assert success_rec["status"] == "completed"
    assert success_rec["automation_id"] == "auto_sync_999"
    assert success_rec["mode"] == "DO"
    assert success_rec["completed_at"] == "2026-11-09T08:00:02Z"

    failed_rec = next(r for r in records if r["id"] == "exec_failed_1")
    assert failed_rec["status"] == "error"
    assert failed_rec["error_code"] == "AUTOMATION_CREATION_FAILED"
    assert failed_rec["mode"] == "AUTOMATE"

    running_rec = next(r for r in records if r["id"] == "exec_running_1")
    assert running_rec["status"] == "running"
    assert running_rec["completed_at"] is None


def test_phase11g_activity_and_executions_tenant_isolation(client, test_store):
    headers_alpha = {"X-Organization-Id": "org-tenant-alpha", "X-User-Id": "user-alpha"}
    headers_beta = {"X-Organization-Id": "org-tenant-beta", "X-User-Id": "user-beta"}

    test_store.save_audit_event("org-tenant-alpha", "AGENT_REQUEST", user_id="user-alpha")
    test_store.save_execution({"id": "exec_alpha_1", "organization_id": "org-tenant-alpha", "mode": "DO", "status": "completed"})

    test_store.save_audit_event("org-tenant-beta", "PLAN_CREATED", user_id="user-beta")
    test_store.save_execution({"id": "exec_beta_1", "organization_id": "org-tenant-beta", "mode": "AUTOMATE", "status": "completed"})

    # Alpha inspection
    act_a = client.get("/api/activity", headers=headers_alpha).json()
    exec_a = client.get("/api/executions", headers=headers_alpha).json()
    assert len(act_a) == 1
    assert act_a[0]["organization_id"] == "org-tenant-alpha"
    assert len(exec_a) == 1
    assert exec_a[0]["id"] == "exec_alpha_1"

    # Beta inspection
    act_b = client.get("/api/activity", headers=headers_beta).json()
    exec_b = client.get("/api/executions", headers=headers_beta).json()
    assert len(act_b) == 1
    assert act_b[0]["organization_id"] == "org-tenant-beta"
    assert len(exec_b) == 1
    assert exec_b[0]["id"] == "exec_beta_1"


def test_phase11g_observability_header_enforcement(client):
    # Missing headers
    assert client.get("/api/activity").status_code == 400
    assert client.get("/api/executions").status_code == 400

    # Wrong header (X-Tenant-ID rejected)
    bad_headers = {"X-Tenant-ID": "org-legacy", "X-User-Id": "user-1"}
    act_res = client.get("/api/activity", headers=bad_headers)
    assert act_res.status_code == 400
    assert "Missing required header 'X-Organization-Id'" in act_res.json()["error"]

    exec_res = client.get("/api/executions", headers=bad_headers)
    assert exec_res.status_code == 400
    assert "Missing required header 'X-Organization-Id'" in exec_res.json()["error"]





