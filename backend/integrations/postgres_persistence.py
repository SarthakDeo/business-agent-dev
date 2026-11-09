"""PostgreSQL persistence implementation for Phase 10.

The store deliberately uses application-generated text IDs so it can preserve
existing Voice2Flow identifiers while remaining independent of the legacy UUID
schema used by the original Docker bootstrap.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from typing import Any, Callable
from uuid import uuid4

from psycopg2.extras import RealDictCursor

from .persistence import _safe_json, _safe_text


class PostgresPersistenceError(RuntimeError):
    """Sanitized database failure exposed to application callers."""


class PostgresStateStore:
    """Tenant-scoped PostgreSQL repository with parameterized SQL only."""

    def __init__(self, dsn: str, connection_factory: Callable | None = None):
        if not dsn:
            raise ValueError("PostgreSQL DSN is required")
        if connection_factory is None:
            import psycopg2
            connection_factory = psycopg2.connect
        self.dsn = dsn
        self._connection_factory = connection_factory
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = None
        try:
            connection = self._connection_factory(self.dsn)
            try:
                cursor = connection.cursor(cursor_factory=RealDictCursor)
            except TypeError:
                cursor = connection.cursor()
            with cursor:
                yield connection, cursor
            connection.commit()
        except Exception as exc:
            if connection is not None:
                connection.rollback()
            raise PostgresPersistenceError("PostgreSQL persistence operation failed") from exc
        finally:
            if connection is not None:
                connection.close()

    def _initialize(self):
        ddl = """
        CREATE TABLE IF NOT EXISTS gnani_credential_references (
            id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, integration TEXT NOT NULL,
            status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_gnani_credentials_org ON gnani_credential_references(organization_id);
        CREATE TABLE IF NOT EXISTS gnani_integration_connections (
            organization_id TEXT NOT NULL, integration TEXT NOT NULL, id TEXT NOT NULL,
            status TEXT NOT NULL, credential_reference TEXT NOT NULL, account_identifier TEXT,
            created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (organization_id, integration)
        );
        CREATE TABLE IF NOT EXISTS gnani_automations (
            id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, n8n_workflow_id TEXT NOT NULL,
            name TEXT NOT NULL, status TEXT NOT NULL, canonical_workflow JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_gnani_automations_org ON gnani_automations(organization_id, created_at);
        CREATE TABLE IF NOT EXISTS gnani_conversations (
            id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, user_id TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_gnani_conversations_owner ON gnani_conversations(organization_id, user_id);
        CREATE TABLE IF NOT EXISTS gnani_conversation_messages (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, organization_id TEXT NOT NULL,
            user_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, mode TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_gnani_messages_conversation ON gnani_conversation_messages(organization_id, conversation_id, created_at);
        CREATE TABLE IF NOT EXISTS gnani_memory (
            id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, user_id TEXT, key TEXT NOT NULL,
            value JSONB NOT NULL, value_type TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL, UNIQUE (organization_id, user_id, key)
        );
        CREATE TABLE IF NOT EXISTS gnani_audit_events (
            id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, user_id TEXT, request_id TEXT,
            run_id TEXT, event_type TEXT NOT NULL, mode TEXT, action TEXT, status TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_gnani_audit_org_created ON gnani_audit_events(organization_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_gnani_audit_request ON gnani_audit_events(request_id);
        CREATE TABLE IF NOT EXISTS gnani_executions (
            id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, user_id TEXT, automation_id TEXT,
            request_id TEXT, mode TEXT NOT NULL, status TEXT NOT NULL, error_code TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb, started_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_gnani_executions_org_started ON gnani_executions(organization_id, started_at);
        CREATE INDEX IF NOT EXISTS idx_gnani_executions_request ON gnani_executions(request_id);
        """
        with self._connect() as (_, cursor):
            cursor.execute(ddl)

    def save_credential_reference(self, reference: Any, created_at: str):
        with self._connect() as (_, cursor):
            cursor.execute(
                """INSERT INTO gnani_credential_references (id, organization_id, integration, status, created_at)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET organization_id=EXCLUDED.organization_id,
                   integration=EXCLUDED.integration, status=EXCLUDED.status""",
                (reference.id, reference.organization_id, reference.integration, reference.status, created_at),
            )

    def get_credential_reference(self, credential_id: str):
        with self._connect() as (_, cursor):
            cursor.execute(
                "SELECT id, organization_id, integration, status FROM gnani_credential_references WHERE id = %s",
                (credential_id,),
            )
            return cursor.fetchone()

    def delete_credential_reference(self, credential_id: str) -> bool:
        with self._connect() as (_, cursor):
            cursor.execute(
                "DELETE FROM gnani_credential_references WHERE id = %s",
                (credential_id,),
            )
            return cursor.rowcount > 0

    def delete_integration_data(self, organization_id: str, integration: str) -> None:
        with self._connect() as (_, cursor):
            cursor.execute(
                "DELETE FROM gnani_credential_references WHERE organization_id = %s AND integration = %s",
                (organization_id, integration),
            )
            cursor.execute(
                "DELETE FROM gnani_integration_connections WHERE organization_id = %s AND integration = %s",
                (organization_id, integration),
            )

    def save_connection(self, connection_data: dict):
        with self._connect() as (_, cursor):
            cursor.execute(
                """INSERT INTO gnani_integration_connections
                   (organization_id, integration, id, status, credential_reference, account_identifier, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (organization_id, integration) DO UPDATE SET id=EXCLUDED.id,
                   status=EXCLUDED.status, credential_reference=EXCLUDED.credential_reference,
                   account_identifier=EXCLUDED.account_identifier, updated_at=EXCLUDED.updated_at""",
                tuple(connection_data[key] for key in (
                    "organization_id", "integration", "id", "status", "credential_reference",
                    "account_identifier", "created_at", "updated_at",
                )),
            )

    def get_connection(self, organization_id: str, integration: str):
        with self._connect() as (_, cursor):
            cursor.execute(
                "SELECT * FROM gnani_integration_connections WHERE organization_id = %s AND integration = %s",
                (organization_id, integration),
            )
            return cursor.fetchone()

    def list_connections(self, organization_id: str):
        with self._connect() as (_, cursor):
            cursor.execute(
                "SELECT * FROM gnani_integration_connections WHERE organization_id = %s ORDER BY integration",
                (organization_id,),
            )
            return cursor.fetchall()

    def save_automation(self, automation: dict):
        now = automation.get("updated_at") or datetime.now(timezone.utc).isoformat()
        with self._connect() as (_, cursor):
            cursor.execute(
                """INSERT INTO gnani_automations
                   (id, organization_id, n8n_workflow_id, name, status, canonical_workflow, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET organization_id=EXCLUDED.organization_id,
                   n8n_workflow_id=EXCLUDED.n8n_workflow_id, name=EXCLUDED.name,
                   status=EXCLUDED.status, canonical_workflow=EXCLUDED.canonical_workflow,
                   updated_at=EXCLUDED.updated_at""",
                (automation["id"], automation["organization_id"], automation["n8n_workflow_id"],
                 automation["name"], automation["status"], json.dumps(_safe_json(automation["canonical_workflow"])),
                 automation.get("created_at", now), now),
            )

    def get_automation(self, organization_id: str, automation_id: str):
        with self._connect() as (_, cursor):
            cursor.execute(
                "SELECT * FROM gnani_automations WHERE organization_id = %s AND id = %s",
                (organization_id, automation_id),
            )
            return cursor.fetchone()

    def list_automations(self, organization_id: str):
        with self._connect() as (_, cursor):
            cursor.execute(
                "SELECT * FROM gnani_automations WHERE organization_id = %s ORDER BY created_at",
                (organization_id,),
            )
            return cursor.fetchall()

    def delete_automation(self, organization_id: str, automation_id: str) -> bool:
        with self._connect() as (_, cursor):
            cursor.execute(
                "DELETE FROM gnani_automations WHERE organization_id = %s AND id = %s",
                (organization_id, automation_id),
            )
            return cursor.rowcount > 0

    def save_conversation_message(self, organization_id: str, user_id: str, role: str, content: str, conversation_id: str | None = None, mode: str | None = None, metadata: dict | None = None):
        now = datetime.now(timezone.utc).isoformat()
        conversation_id = conversation_id or f"conv_{uuid4().hex}"
        message_id = f"msg_{uuid4().hex}"
        with self._connect() as (_, cursor):
            cursor.execute(
                """INSERT INTO gnani_conversations (id, organization_id, user_id, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET updated_at=EXCLUDED.updated_at""",
                (conversation_id, organization_id, user_id, now, now),
            )
            cursor.execute(
                """INSERT INTO gnani_conversation_messages
                   (id, conversation_id, organization_id, user_id, role, content, mode, metadata, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (message_id, conversation_id, organization_id, user_id, role, _safe_text(content), mode,
                 json.dumps(_safe_json(metadata or {})), now),
            )
        return {"id": message_id, "conversation_id": conversation_id, "organization_id": organization_id, "user_id": user_id, "role": role, "content": _safe_text(content), "mode": mode, "metadata": _safe_json(metadata or {}), "created_at": now}

    def list_conversation_messages(self, organization_id: str, conversation_id: str):
        with self._connect() as (_, cursor):
            cursor.execute(
                "SELECT * FROM gnani_conversation_messages WHERE organization_id = %s AND conversation_id = %s ORDER BY created_at",
                (organization_id, conversation_id),
            )
            return cursor.fetchall()

    def save_memory(self, organization_id: str, user_id: str | None, key: str, value: Any, value_type: str = "json"):
        now = datetime.now(timezone.utc).isoformat()
        memory_id = f"mem_{uuid4().hex}"
        safe_value = _safe_json(value)
        with self._connect() as (_, cursor):
            cursor.execute(
                """INSERT INTO gnani_memory (id, organization_id, user_id, key, value, value_type, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (organization_id, user_id, key) DO UPDATE SET value=EXCLUDED.value,
                   value_type=EXCLUDED.value_type, updated_at=EXCLUDED.updated_at""",
                (memory_id, organization_id, user_id, key, json.dumps(safe_value), value_type, now, now),
            )
        return {"id": memory_id, "organization_id": organization_id, "user_id": user_id, "key": key, "value": safe_value, "value_type": value_type, "created_at": now, "updated_at": now}

    def get_memory(self, organization_id: str, user_id: str | None, key: str):
        with self._connect() as (_, cursor):
            cursor.execute(
                """SELECT * FROM gnani_memory
                WHERE organization_id = %s AND user_id IS NOT DISTINCT FROM %s AND key = %s""",
                (organization_id, user_id, key),
            )
            return cursor.fetchone()

    def save_audit_event(self, organization_id: str, event_type: str, **event):
        now = datetime.now(timezone.utc).isoformat()
        record = {"id": f"audit_{uuid4().hex}", "organization_id": organization_id, "user_id": event.get("user_id"), "request_id": event.get("request_id"), "run_id": event.get("run_id"), "event_type": event_type, "mode": event.get("mode"), "action": event.get("action"), "status": event.get("status"), "metadata": _safe_json(event.get("metadata", {})), "created_at": now}
        with self._connect() as (_, cursor):
            cursor.execute(
                """INSERT INTO gnani_audit_events (id, organization_id, user_id, request_id, run_id, event_type, mode, action, status, metadata, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (record["id"], organization_id, record["user_id"], record["request_id"], record["run_id"], event_type, record["mode"], record["action"], record["status"], json.dumps(record["metadata"]), now),
            )
        return record

    def save_execution(self, execution: dict):
        record = dict(execution)
        record.setdefault("id", f"exec_{uuid4().hex}")
        record.setdefault("started_at", datetime.now(timezone.utc).isoformat())
        record.setdefault("metadata", {})
        with self._connect() as (_, cursor):
            cursor.execute(
                """INSERT INTO gnani_executions (id, organization_id, user_id, automation_id, request_id, mode, status, error_code, metadata, started_at, completed_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (record["id"], record["organization_id"], record.get("user_id"), record.get("automation_id"), record.get("request_id"), record["mode"], record["status"], record.get("error_code"), json.dumps(_safe_json(record["metadata"])), record["started_at"], record.get("completed_at")),
            )
        return record

    def list_audit_events(self, organization_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
        with self._connect() as (_, cursor):
            cursor.execute(
                """SELECT id, organization_id, user_id, request_id, run_id, event_type, mode, action, status, metadata, created_at
                   FROM gnani_audit_events
                   WHERE organization_id = %s
                   ORDER BY created_at DESC
                   LIMIT %s OFFSET %s""",
                (organization_id, max(1, min(limit, 100)), max(0, offset)),
            )
            return cursor.fetchall()

    def list_executions(self, organization_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
        with self._connect() as (_, cursor):
            cursor.execute(
                """SELECT id, organization_id, user_id, automation_id, request_id, mode, status, error_code, metadata, started_at, completed_at
                   FROM gnani_executions
                   WHERE organization_id = %s
                   ORDER BY started_at DESC
                   LIMIT %s OFFSET %s""",
                (organization_id, max(1, min(limit, 100)), max(0, offset)),
            )
            return cursor.fetchall()

    def get_dashboard_stats(self, organization_id: str) -> dict:
        with self._connect() as (_, cursor):
            cursor.execute(
                """SELECT
                    (SELECT COUNT(*) FROM gnani_automations WHERE organization_id = %s) AS automations,
                    (SELECT COUNT(*) FROM gnani_automations WHERE organization_id = %s AND status IN ('created', 'updated', 'active')) AS active_automations,
                    (SELECT COUNT(*) FROM gnani_integration_connections WHERE organization_id = %s AND status = 'connected') AS integrations,
                    (SELECT COUNT(*) FROM gnani_executions WHERE organization_id = %s) AS recent_executions,
                    (SELECT COUNT(*) FROM gnani_executions WHERE organization_id = %s AND status = 'error') AS recent_errors""",
                (organization_id, organization_id, organization_id, organization_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                return {"automations": 0, "active_automations": 0, "integrations": 0, "recent_executions": 0, "recent_errors": 0}
            return {
                "automations": int(row.get("automations", 0)),
                "active_automations": int(row.get("active_automations", 0)),
                "integrations": int(row.get("integrations", 0)),
                "recent_executions": int(row.get("recent_executions", 0)),
                "recent_errors": int(row.get("recent_errors", 0)),
            }
