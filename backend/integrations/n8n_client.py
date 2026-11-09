"""Centralized, injectable communication boundary for n8n."""

from dataclasses import dataclass
from typing import Any, Optional

import requests


class N8nError(Exception):
    """Safe, normalized n8n failure."""

    def __init__(self, code: str, message: str, status_code: int | None = None):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class N8nConfig:
    base_url: str
    api_key: str = ""
    timeout: float = 30.0


class N8nClient:
    """Small n8n REST client; transport is injectable for deterministic tests."""

    def __init__(self, config: N8nConfig, session: Any = requests):
        if not config.base_url:
            raise ValueError("n8n base URL is required")
        self.config = config
        self.session = session

    # ------------------------------------------------------------------
    # Public REST API methods — all use /api/v1 prefix
    # ------------------------------------------------------------------

    def health_check(self) -> dict:
        """Health endpoint lives at root, not under /api/v1."""
        return self._request("GET", "/healthz")

    def create_workflow(self, workflow: dict) -> dict:
        return self._rest("POST", "/workflows", workflow)

    def get_workflow(self, workflow_id: str) -> dict:
        return self._rest("GET", f"/workflows/{workflow_id}")

    def update_workflow(self, workflow_id: str, workflow: dict) -> dict:
        return self._rest("PUT", f"/workflows/{workflow_id}", workflow)

    def delete_workflow(self, workflow_id: str) -> dict:
        return self._rest("DELETE", f"/workflows/{workflow_id}")

    def activate_workflow(self, workflow_id: str) -> dict:
        return self._rest("POST", f"/workflows/{workflow_id}/activate")

    def deactivate_workflow(self, workflow_id: str) -> dict:
        return self._rest("POST", f"/workflows/{workflow_id}/deactivate")

    def execute_workflow(self, workflow_id: str, data: Optional[dict] = None) -> dict:
        response = self._rest("POST", f"/workflows/{workflow_id}/run", data or {})
        execution_id = response.get("executionId") or response.get("id")
        if not execution_id:
            raise N8nError("MALFORMED_RESPONSE", "n8n returned no execution ID")
        return {
            "status": response.get("status", "queued"),
            "execution_id": str(execution_id),
            "result": response.get("data", response.get("result", {})),
        }

    def invoke_webhook(self, workflow_id: str, data: Optional[dict] = None) -> dict:
        """Invoke a compatibility webhook — path is /webhook/..., NOT /api/v1/webhook/..."""
        return self._request("POST", f"/webhook/{workflow_id}", data or {})

    def get_execution(self, execution_id: str) -> dict:
        response = self._rest("GET", f"/executions/{execution_id}")
        returned_id = response.get("id") or response.get("executionId")
        if not returned_id:
            raise N8nError("MALFORMED_RESPONSE", "n8n returned no execution ID")
        return {
            "status": response.get("status", "unknown"),
            "execution_id": str(returned_id),
            "result": response.get("data", response.get("result", {})),
        }

    def create_credential(self, credential_type: str, name: str, data: dict) -> dict:
        response = self._rest(
            "POST",
            "/credentials",
            {"type": credential_type, "name": name, "data": data},
        )
        if not response.get("id"):
            raise N8nError("MALFORMED_RESPONSE", "n8n returned no credential ID")
        return response

    def delete_credential(self, credential_id: str) -> dict:
        return self._rest("DELETE", f"/credentials/{credential_id}")

    def _rest(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        """Route a call through the n8n REST API (all paths are under /api/v1)."""
        return self._request(method, f"/api/v1{path}", payload)

    def _request(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.config.api_key:
            headers["X-N8N-API-KEY"] = self.config.api_key
        try:
            response = self.session.request(
                method,
                f"{self.config.base_url.rstrip('/')}{path}",
                json=payload,
                headers=headers,
                timeout=self.config.timeout,
            )
        except requests.Timeout as exc:
            raise N8nError("TIMEOUT", "n8n request timed out") from exc
        except requests.RequestException as exc:
            raise N8nError("CONNECTION_FAILED", "n8n is unreachable") from exc

        if response.status_code in (401, 403):
            raise N8nError("AUTHENTICATION_FAILED", "n8n authentication failed", response.status_code)
        if response.status_code == 404 and path.startswith(("/api/v1/workflows/", "/api/v1/executions/")):
            raise N8nError("NOT_FOUND", "n8n workflow or execution was not found", 404)
        if response.status_code >= 400:
            code = "EXECUTION_FAILED" if path.startswith("/api/v1/workflows/") and path.endswith("/run") else "N8N_REQUEST_FAILED"
            raise N8nError(code, "n8n rejected the request", response.status_code)
        if response.status_code == 204:
            return {}

        try:
            data = response.json()
        except (ValueError, TypeError) as exc:
            raise N8nError("MALFORMED_RESPONSE", "n8n returned malformed JSON", response.status_code) from exc
        if not isinstance(data, dict):
            raise N8nError("MALFORMED_RESPONSE", "n8n returned an invalid response", response.status_code)
        return data