from unittest.mock import patch

from backend.agent.agent import Agent
from backend.agent.context_manager import ConversationContext
from backend.integrations import IntegrationManager, IntegrationStateStore, PostgresStateStore


def test_sqlite_phase10_records_are_tenant_scoped_and_sanitized(tmp_path):
    store = IntegrationStateStore(tmp_path / "phase10.sqlite3")
    message = store.save_conversation_message(
        "org-a", "user-a", "user", "api_key=SECRET_VALUE", metadata={"token": "SECRET_VALUE"}
    )
    assert "SECRET_VALUE" not in str(message)
    assert store.list_conversation_messages("org-b", message["conversation_id"]) == []

    memory = store.save_memory("org-a", "user-a", "preference", {"value": "dark"})
    assert store.get_memory("org-b", "user-a", "preference") is None
    assert store.get_memory("org-a", "user-a", "preference")["value"] == {"value": "dark"}

    audit = store.save_audit_event(
        "org-a", "TOOL_EXECUTION_COMPLETED", user_id="user-a", metadata={"password": "SECRET_VALUE"}
    )
    assert "SECRET_VALUE" not in str(audit)

    execution = store.save_execution({
        "organization_id": "org-a", "user_id": "user-a", "mode": "DO", "status": "completed",
        "metadata": {"access_token": "SECRET_VALUE"},
    })
    assert execution["id"].startswith("exec_")


def test_agent_records_request_and_plan_audit_without_raw_plan_data():
    manager = IntegrationManager()
    context = ConversationContext("user-a", "org-a", integration_manager=manager)
    plan = {
        "mode": "ASK",
        "goal": "Count delayed orders",
        "steps": [{"id": "step_1", "tool": "crm.find_order", "parameters": {"status": "delayed"}}],
    }

    with patch("backend.agent.agent.plan", return_value=plan):
        result = Agent(manager).run("How many delayed orders?", context, ["crm.read"], dry_run=True)

    assert result.status == "completed"
    with manager._state_store._connect() as connection:
        events = connection.execute(
            "SELECT event_type, run_id, metadata FROM audit_events WHERE organization_id = ? ORDER BY created_at",
            ("org-a",),
        ).fetchall()
    assert [row["event_type"] for row in events] == ["AGENT_REQUEST", "PLAN_CREATED"]
    assert all(row["run_id"] == context.run_id for row in events)
    assert "delayed" not in str(events)


class FakeCursor:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        return {"id": "cred-1", "organization_id": "org-a", "integration": "crm", "status": "active"}

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, **kwargs):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_postgres_store_uses_parameterized_sql_and_never_persists_raw_secret():
    connections = []

    def factory(_dsn):
        connection = FakeConnection()
        connections.append(connection)
        return connection

    store = PostgresStateStore("postgresql://test", connection_factory=factory)
    reference = type("Reference", (), {
        "id": "cred-1", "organization_id": "org-a", "integration": "crm", "status": "active"
    })()
    store.save_credential_reference(reference, "2026-01-01T00:00:00Z")

    calls = [call for connection in connections for call in connection.cursor_instance.calls]
    credential_call = next(call for call in calls if "gnani_credential_references" in call[0] and "INSERT" in call[0])
    assert "SECRET_VALUE" not in str(credential_call)
    assert "%s" in credential_call[0]
    assert connections[-1].committed is True


def test_real_docker_postgres_live_verification():
    import socket
    import pytest

    s = socket.socket()
    s.settimeout(1.0)
    try:
        if s.connect_ex(("localhost", 5432)) != 0:
            pytest.skip("Docker PostgreSQL is not reachable on localhost:5432")
    except Exception:
        pytest.skip("Docker PostgreSQL is not reachable on localhost:5432")
    finally:
        s.close()

    dsn = "postgresql://gnani_test:gnani_test_password@localhost:5432/gnani_test"
    store = PostgresStateStore(dsn)

    # 1. Schema check
    with store._connect() as (_, cursor):
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = {row["table_name"] for row in cursor.fetchall()}
    expected_tables = {
        "gnani_credential_references", "gnani_integration_connections", "gnani_automations",
        "gnani_conversations", "gnani_conversation_messages", "gnani_memory",
        "gnani_audit_events", "gnani_executions",
    }
    assert expected_tables.issubset(tables)

    # 2. Credential reference CRUD
    ref = type("Reference", (), {
        "id": "cred_live_test", "organization_id": "org_live_a", "integration": "crm", "status": "active"
    })()
    store.save_credential_reference(ref, "2026-11-09T00:00:00Z")
    saved_ref = store.get_credential_reference("cred_live_test")
    assert saved_ref["id"] == "cred_live_test"
    assert saved_ref["organization_id"] == "org_live_a"

    # 3. Connection CRUD
    conn_data = {
        "organization_id": "org_live_a", "integration": "crm", "id": "conn_live_test",
        "status": "connected", "credential_reference": "cred_live_test", "account_identifier": "test@gnani.ai",
        "created_at": "2026-11-09T00:00:00Z", "updated_at": "2026-11-09T00:00:00Z"
    }
    store.save_connection(conn_data)
    saved_conn = store.get_connection("org_live_a", "crm")
    assert saved_conn["credential_reference"] == "cred_live_test"

    # 4. Automations CREATE and MODIFY
    auto_data = {
        "id": "auto_live_test", "organization_id": "org_live_a", "n8n_workflow_id": "wf_live_123",
        "name": "Live Docker Test Auto", "status": "created",
        "canonical_workflow": {"name": "Test", "steps": [{"tool": "crm.find_order"}]},
        "created_at": "2026-11-09T00:00:00Z", "updated_at": "2026-11-09T00:00:00Z"
    }
    store.save_automation(auto_data)
    created_auto = store.get_automation("org_live_a", "auto_live_test")
    assert created_auto["status"] == "created"

    # Modify
    auto_data["status"] = "updated"
    auto_data["canonical_workflow"]["steps"].append({"tool": "slack.send_message"})
    store.save_automation(auto_data)
    updated_auto = store.get_automation("org_live_a", "auto_live_test")
    assert updated_auto["id"] == "auto_live_test"
    assert updated_auto["status"] == "updated"
    assert len(updated_auto["canonical_workflow"]["steps"]) == 2

    # 5. Conversations & Messages
    msg = store.save_conversation_message(
        "org_live_a", "user_1", "user", "Test message with token=TEST_SECRET_DO_NOT_PERSIST_123",
        conversation_id="conv_live_test", mode="ASK", metadata={"api_key": "TEST_SECRET_DO_NOT_PERSIST_123"}
    )
    assert "TEST_SECRET_DO_NOT_PERSIST_123" not in str(msg)
    assert "[REDACTED]" in str(msg)

    # 6. Memory
    mem = store.save_memory("org_live_a", "user_1", "color_pref", {"theme": "dark", "secret": "TEST_SECRET_DO_NOT_PERSIST_123"})
    assert "TEST_SECRET_DO_NOT_PERSIST_123" not in str(mem)
    fetched_mem = store.get_memory("org_live_a", "user_1", "color_pref")
    assert fetched_mem["value"]["theme"] == "dark"

    # 7. Audit & Execution
    audit = store.save_audit_event("org_live_a", "AGENT_REQUEST", user_id="user_1", request_id="req_live_test", run_id="run_live_test", metadata={"password": "TEST_SECRET_DO_NOT_PERSIST_123"})
    assert "TEST_SECRET_DO_NOT_PERSIST_123" not in str(audit)

    exec_rec = store.save_execution({
        "organization_id": "org_live_a", "user_id": "user_1", "automation_id": "auto_live_test",
        "request_id": "req_live_test", "mode": "DO", "status": "completed",
        "metadata": {"token": "TEST_SECRET_DO_NOT_PERSIST_123"}
    })
    # Query database directly to confirm persisted record is sanitized
    with store._connect() as (_, cursor):
        cursor.execute("SELECT * FROM gnani_executions WHERE id = %s", (exec_rec["id"],))
        db_exec = cursor.fetchone()
    assert "TEST_SECRET_DO_NOT_PERSIST_123" not in str(db_exec)
    assert "[REDACTED]" in str(db_exec)

    # 8. Tenant isolation
    assert store.get_connection("org_live_b", "crm") is None
    assert store.get_automation("org_live_b", "auto_live_test") is None
    assert store.list_conversation_messages("org_live_b", "conv_live_test") == []
    assert store.get_memory("org_live_b", "user_1", "color_pref") is None

    # 9. Real Agent -> PostgresStateStore flow
    from backend.agent.agent import Agent
    from backend.agent.context_manager import ConversationContext
    from backend.integrations import IntegrationManager
    from unittest.mock import patch

    mgr = IntegrationManager(state_store=store)
    ctx = ConversationContext("user_live", "org_live_a", integration_manager=mgr)
    agent_inst = Agent(integration_manager=mgr)

    plan_mock = {
        "mode": "ASK",
        "goal": "Check orders",
        "steps": [{"id": "step_1", "tool": "crm.find_order", "parameters": {"status": "delayed"}}]
    }
    with patch("backend.agent.agent.plan", return_value=plan_mock):
        resp = agent_inst.run("Check orders", ctx, ["crm.read"], dry_run=True)
    assert resp.status == "completed"

    with store._connect() as (_, cursor):
        cursor.execute(
            "SELECT event_type FROM gnani_audit_events WHERE organization_id = %s AND run_id = %s ORDER BY created_at",
            ("org_live_a", resp.run_id)
        )
        rows = cursor.fetchall()
    assert [r["event_type"] for r in rows] == ["AGENT_REQUEST", "PLAN_CREATED"]

