"""Persistence for integration metadata and opaque credential references.

The SQLite backend keeps the demo self-contained. Deployments with a
PostgreSQL DSN can provide a compatible repository implementation later
without changing IntegrationManager or CredentialManager.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any
from uuid import uuid4


_SENSITIVE_KEY_RE = re.compile(r"(?:secret|token|password|api[_-]?key|authorization|client[_-]?secret)", re.IGNORECASE)
_SENSITIVE_VALUE_RE = re.compile(r"(?i)(secret|token|password|api[_-]?key|authorization)\s*[:=]\s*[^\s,;]+")


def _safe_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _SENSITIVE_KEY_RE.search(str(key)) else _safe_json(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_safe_json(child) for child in value]
    if isinstance(value, str):
        return _SENSITIVE_VALUE_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    return value


def _safe_text(value: str) -> str:
    return _SENSITIVE_VALUE_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


class IntegrationStateStore:
    """Durable metadata store; raw credential values are never persisted."""

    def __init__(self, path: str | Path = "database/integration_state.sqlite3"):
        self.path = str(path)
        self._memory_connection = None
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        is_memory = self.path == ":memory:"
        if is_memory:
            if self._memory_connection is None:
                self._memory_connection = sqlite3.connect(self.path)
                self._memory_connection.row_factory = sqlite3.Row
            connection = self._memory_connection
        else:
            connection = sqlite3.connect(self.path)
            connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            if not is_memory:
                connection.close()

    def _initialize(self):
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS credential_references (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    integration TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS integration_connections (
                    organization_id TEXT NOT NULL,
                    integration TEXT NOT NULL,
                    id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    credential_reference TEXT NOT NULL,
                    account_identifier TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (organization_id, integration)
                );
                CREATE TABLE IF NOT EXISTS automations (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    n8n_workflow_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    canonical_workflow TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    mode TEXT,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    user_id TEXT,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    value_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (organization_id, user_id, key)
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    user_id TEXT,
                    request_id TEXT,
                    run_id TEXT,
                    event_type TEXT NOT NULL,
                    mode TEXT,
                    action TEXT,
                    status TEXT,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    user_id TEXT,
                    automation_id TEXT,
                    request_id TEXT,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_code TEXT,
                    metadata TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_conversations_org_user ON conversations(organization_id, user_id);
                CREATE INDEX IF NOT EXISTS idx_messages_org_created ON conversation_messages(organization_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_audit_org_created ON audit_events(organization_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_executions_org_created ON executions(organization_id, started_at);
                """
            )

    def save_credential_reference(self, reference: Any, created_at: str):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO credential_references
                (id, organization_id, integration, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (reference.id, reference.organization_id, reference.integration,
                 reference.status, created_at),
            )

    def get_credential_reference(self, credential_id: str):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, organization_id, integration, status "
                "FROM credential_references WHERE id = ?",
                (credential_id,),
            ).fetchone()
        return dict(row) if row else None

    def delete_credential_reference(self, credential_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM credential_references WHERE id = ?",
                (credential_id,),
            )
            connection.commit()
            return cursor.rowcount > 0

    def delete_integration_data(self, organization_id: str, integration: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM credential_references WHERE organization_id = ? AND integration = ?",
                (organization_id, integration),
            )
            connection.execute(
                "DELETE FROM integration_connections WHERE organization_id = ? AND integration = ?",
                (organization_id, integration),
            )
            connection.commit()

    def save_connection(self, connection_data: dict):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO integration_connections
                (organization_id, integration, id, status, credential_reference,
                 account_identifier, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(connection_data[key] for key in (
                    "organization_id", "integration", "id", "status",
                    "credential_reference", "account_identifier", "created_at",
                    "updated_at",
                )),
            )

    def get_connection(self, organization_id: str, integration: str):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM integration_connections "
                "WHERE organization_id = ? AND integration = ?",
                (organization_id, integration),
            ).fetchone()
        return dict(row) if row else None

    def list_connections(self, organization_id: str):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM integration_connections WHERE organization_id = ?",
                (organization_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_automation(self, automation: dict):
        now = automation.get("updated_at") or datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO automations
                (id, organization_id, n8n_workflow_id, name, status,
                 canonical_workflow, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    automation["id"],
                    automation["organization_id"],
                    automation["n8n_workflow_id"],
                    automation["name"],
                    automation["status"],
                    json.dumps(_safe_json(automation["canonical_workflow"]), sort_keys=True),
                    automation.get("created_at", now),
                    now,
                ),
            )

    def get_automation(self, organization_id: str, automation_id: str):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM automations WHERE organization_id = ? AND id = ?",
                (organization_id, automation_id),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["canonical_workflow"] = json.loads(result["canonical_workflow"])
        return result

    def list_automations(self, organization_id: str):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM automations WHERE organization_id = ? ORDER BY created_at",
                (organization_id,),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["canonical_workflow"] = json.loads(item["canonical_workflow"])
            results.append(item)
        return results

    def delete_automation(self, organization_id: str, automation_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM automations WHERE organization_id = ? AND id = ?",
                (organization_id, automation_id),
            )
            connection.commit()
            return cursor.rowcount > 0

    def save_conversation_message(
        self, organization_id: str, user_id: str, role: str, content: str,
        conversation_id: str | None = None, mode: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        conversation_id = conversation_id or f"conv_{uuid4().hex}"
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO conversations (id, organization_id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, organization_id, user_id, now, now),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ? AND organization_id = ?",
                (now, conversation_id, organization_id),
            )
            message = {
                "id": f"msg_{uuid4().hex}", "conversation_id": conversation_id,
                "organization_id": organization_id, "user_id": user_id,
                "role": role, "content": _safe_text(content), "mode": mode,
                "metadata": _safe_json(metadata or {}), "created_at": now,
            }
            connection.execute(
                "INSERT INTO conversation_messages (id, conversation_id, organization_id, user_id, role, content, mode, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (message["id"], conversation_id, organization_id, user_id, role,
                 message["content"], mode, json.dumps(message["metadata"], sort_keys=True), now),
            )
        return message

    def list_conversation_messages(self, organization_id: str, conversation_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM conversation_messages WHERE organization_id = ? AND conversation_id = ? ORDER BY created_at",
                (organization_id, conversation_id),
            ).fetchall()
        return [{**dict(row), "metadata": json.loads(row["metadata"])} for row in rows]

    def save_memory(self, organization_id: str, user_id: str | None, key: str, value: Any, value_type: str = "json") -> dict:
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": f"mem_{uuid4().hex}", "organization_id": organization_id,
            "user_id": user_id, "key": key, "value": _safe_json(value),
            "value_type": value_type, "created_at": now, "updated_at": now,
        }
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id, created_at FROM memories WHERE organization_id = ? AND user_id IS ? AND key = ?",
                (organization_id, user_id, key),
            ).fetchone()
            if existing:
                record["id"] = existing["id"]
                record["created_at"] = existing["created_at"]
            connection.execute(
                "INSERT OR REPLACE INTO memories (id, organization_id, user_id, key, value, value_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (record["id"], organization_id, user_id, key, json.dumps(record["value"], sort_keys=True), value_type, record["created_at"], now),
            )
        return record

    def get_memory(self, organization_id: str, user_id: str | None, key: str):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM memories WHERE organization_id = ? AND user_id IS ? AND key = ?",
                (organization_id, user_id, key),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["value"] = json.loads(result["value"])
        return result

    def save_audit_event(self, organization_id: str, event_type: str, **event) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": f"audit_{uuid4().hex}", "organization_id": organization_id,
            "user_id": event.get("user_id"), "request_id": event.get("request_id"),
            "run_id": event.get("run_id"), "event_type": event_type,
            "mode": event.get("mode"), "action": event.get("action"),
            "status": event.get("status"), "metadata": _safe_json(event.get("metadata", {})),
            "created_at": now,
        }
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO audit_events (id, organization_id, user_id, request_id, run_id, event_type, mode, action, status, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (record["id"], organization_id, record["user_id"], record["request_id"], record["run_id"], event_type, record["mode"], record["action"], record["status"], json.dumps(record["metadata"], sort_keys=True), now),
            )
        return record

    def save_execution(self, execution: dict) -> dict:
        record = dict(execution)
        record.setdefault("id", f"exec_{uuid4().hex}")
        record.setdefault("started_at", datetime.now(timezone.utc).isoformat())
        record.setdefault("metadata", {})
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO executions (id, organization_id, user_id, automation_id, request_id, mode, status, error_code, metadata, started_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (record["id"], record["organization_id"], record.get("user_id"), record.get("automation_id"), record.get("request_id"), record["mode"], record["status"], record.get("error_code"), json.dumps(_safe_json(record["metadata"]), sort_keys=True), record["started_at"], record.get("completed_at")),
            )
        return record

    def list_audit_events(self, organization_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, organization_id, user_id, request_id, run_id, event_type, mode, action, status, metadata, created_at FROM audit_events WHERE organization_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (organization_id, max(1, min(limit, 100)), max(0, offset)),
            ).fetchall()
        return [{**dict(row), "metadata": json.loads(row["metadata"])} for row in rows]

    def list_executions(self, organization_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, organization_id, user_id, automation_id, request_id, mode, status, error_code, metadata, started_at, completed_at FROM executions WHERE organization_id = ? ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (organization_id, max(1, min(limit, 100)), max(0, offset)),
            ).fetchall()
        return [{**dict(row), "metadata": json.loads(row["metadata"])} for row in rows]

    def get_dashboard_stats(self, organization_id: str) -> dict:
        with self._connect() as connection:
            automations = connection.execute("SELECT COUNT(*) FROM automations WHERE organization_id = ?", (organization_id,)).fetchone()[0]
            active_automations = connection.execute("SELECT COUNT(*) FROM automations WHERE organization_id = ? AND status IN ('created', 'updated', 'active')", (organization_id,)).fetchone()[0]
            integrations = connection.execute("SELECT COUNT(*) FROM integration_connections WHERE organization_id = ? AND status = 'connected'", (organization_id,)).fetchone()[0]
            recent_executions = connection.execute("SELECT COUNT(*) FROM executions WHERE organization_id = ?", (organization_id,)).fetchone()[0]
            recent_errors = connection.execute("SELECT COUNT(*) FROM executions WHERE organization_id = ? AND status = 'error'", (organization_id,)).fetchone()[0]
        return {
            "automations": int(automations),
            "active_automations": int(active_automations),
            "integrations": int(integrations),
            "recent_executions": int(recent_executions),
            "recent_errors": int(recent_errors),
        }
