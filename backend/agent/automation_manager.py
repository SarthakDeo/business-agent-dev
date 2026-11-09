"""Phase 6 orchestration for creating persistent n8n automations."""

from copy import deepcopy
from datetime import datetime, timezone
import logging
import re
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

from .workflow_compiler import WorkflowCompilationError, WorkflowCompiler, WorkflowValidator
from .tool_registry import get_tool
from ..integrations import IntegrationManager, N8nClient, N8nError
from ..integrations.persistence import IntegrationStateStore


class AutomationCreationError(Exception):
    """Safe, structured failure from the automation creation boundary."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class AutomationNotFoundError(Exception):
    def __init__(self, message: str, code: str = "AUTOMATION_NOT_FOUND"):
        self.code = code
        self.message = message
        super().__init__(message)


class AutomationAmbiguousError(Exception):
    def __init__(self, message: str, matches: list[dict] = None, code: str = "AUTOMATION_AMBIGUOUS"):
        self.code = code
        self.message = message
        self.matches = matches or []
        super().__init__(message)


class InvalidModificationError(Exception):
    def __init__(self, message: str, code: str = "INVALID_MODIFICATION"):
        self.code = code
        self.message = message
        super().__init__(message)


def apply_modification(canonical_workflow: dict, modification: dict) -> dict:
    if not isinstance(canonical_workflow, dict):
        raise InvalidModificationError("Canonical workflow must be an object")
    if not isinstance(modification, dict):
        raise InvalidModificationError("Modification must be an object")

    operation = (modification.get("operation") or modification.get("action") or "").upper().strip()
    if not operation:
        raise InvalidModificationError("Modification operation is required")

    modified = deepcopy(canonical_workflow)
    steps = modified.get("steps")
    if not isinstance(steps, list):
        raise InvalidModificationError("Workflow steps must be a list")

    if operation == "ADD_STEP":
        step = modification.get("step")
        if not isinstance(step, dict):
            raise InvalidModificationError("ADD_STEP requires a 'step' object")
        step_id = step.get("id")
        if not isinstance(step_id, str) or not step_id.strip():
            raise InvalidModificationError("Step must have a non-empty 'id'")
        if any(s.get("id") == step_id for s in steps):
            raise InvalidModificationError(f"Step with id '{step_id}' already exists")
        if not isinstance(step.get("tool"), str) or not step["tool"].strip():
            raise InvalidModificationError("Step must specify a 'tool'")

        after_step = modification.get("after_step")
        insert_at = modification.get("insert_at") or modification.get("position")
        if after_step:
            idx = next((i for i, s in enumerate(steps) if s.get("id") == after_step), None)
            if idx is None:
                raise InvalidModificationError(f"Step '{after_step}' not found to insert after")
            steps.insert(idx + 1, deepcopy(step))
        elif isinstance(insert_at, int) and 0 <= insert_at <= len(steps):
            steps.insert(insert_at, deepcopy(step))
        else:
            steps.append(deepcopy(step))

    elif operation == "REMOVE_STEP":
        step_id = modification.get("step_id")
        if not isinstance(step_id, str) or not step_id.strip():
            raise InvalidModificationError("REMOVE_STEP requires 'step_id'")
        idx = next((i for i, s in enumerate(steps) if s.get("id") == step_id), None)
        if idx is None:
            raise InvalidModificationError(f"Step with id '{step_id}' not found")
        if len(steps) <= 1:
            raise InvalidModificationError("Cannot remove all steps; workflow must have at least one step")
        steps.pop(idx)

    elif operation == "REPLACE_STEP":
        step_id = modification.get("step_id")
        step = modification.get("step")
        if not isinstance(step_id, str) or not step_id.strip():
            raise InvalidModificationError("REPLACE_STEP requires 'step_id'")
        if not isinstance(step, dict):
            raise InvalidModificationError("REPLACE_STEP requires a 'step' object")
        idx = next((i for i, s in enumerate(steps) if s.get("id") == step_id), None)
        if idx is None:
            raise InvalidModificationError(f"Step with id '{step_id}' not found")

        replacement = deepcopy(step)
        if "id" not in replacement:
            replacement["id"] = step_id
        elif replacement["id"] != step_id and any(s.get("id") == replacement["id"] for i, s in enumerate(steps) if i != idx):
            raise InvalidModificationError(f"Duplicate step ID '{replacement['id']}'")
        if not isinstance(replacement.get("tool"), str) or not replacement["tool"].strip():
            raise InvalidModificationError("Step must specify a 'tool'")

        steps[idx] = replacement

    elif operation == "UPDATE_PARAMETERS":
        step_id = modification.get("step_id")
        parameters = modification.get("parameters")
        if not isinstance(step_id, str) or not step_id.strip():
            raise InvalidModificationError("UPDATE_PARAMETERS requires 'step_id'")
        if not isinstance(parameters, dict):
            raise InvalidModificationError("UPDATE_PARAMETERS requires a 'parameters' object")
        target_step = next((s for s in steps if s.get("id") == step_id), None)
        if target_step is None:
            raise InvalidModificationError(f"Step with id '{step_id}' not found")
        target_step.setdefault("parameters", {}).update(deepcopy(parameters))

    else:
        raise InvalidModificationError(f"Unsupported modification operation: '{operation}'")

    if "name" in modification and isinstance(modification["name"], str) and modification["name"].strip():
        modified["name"] = _safe_automation_name(modification["name"])
    if "trigger" in modification and isinstance(modification["trigger"], dict):
        modified["trigger"] = deepcopy(modification["trigger"])

    return modified


def canonical_workflow_from_plan(plan: dict) -> dict:
    """Convert a validated Agent plan into the canonical workflow schema."""
    if not isinstance(plan, dict) or plan.get("mode") != "AUTOMATE":
        raise AutomationCreationError("INVALID_WORKFLOW", "Automation plan must use AUTOMATE mode")

    config = plan.get("automation_config") or {}
    trigger = deepcopy(plan.get("trigger"))
    if trigger is None:
        trigger = {
            "type": config.get("trigger_type", "webhook"),
            "parameters": deepcopy(config.get("trigger_config") or {}),
        }
    if isinstance(trigger, dict):
        tool = trigger.get("tool")
        if not tool and trigger.get("type") == "webhook":
            tool = "webhook.received"
            trigger["tool"] = tool
        elif tool and not trigger.get("type"):
            if tool.startswith("schedule."):
                trigger["type"] = "schedule"
            elif tool == "webhook.received":
                trigger["type"] = "webhook"
            else:
                trigger["type"] = "event"

        if not isinstance(trigger.get("parameters"), dict):
            trigger["parameters"] = {}
        if trigger.get("type") == "webhook" and "path" not in trigger["parameters"]:
            trigger["parameters"]["path"] = "webhook"

    steps = []
    for step in plan.get("steps", []):
        steps.append({
            "id": step.get("id"),
            "tool": step.get("tool"),
            "parameters": deepcopy(step.get("parameters", {})),
        })

    name = _safe_automation_name(plan.get("name") or config.get("name"))
    return {
        "mode": "AUTOMATE",
        "name": name,
        "trigger": trigger,
        "steps": steps,
    }


def _safe_automation_name(name: Optional[str]) -> str:
    if not isinstance(name, str) or not name.strip():
        return "Voice2Flow Automation"
    cleaned = re.sub(r"[^A-Za-z0-9 _:+&/-]", "", name).strip()
    return cleaned[:120] or "Voice2Flow Automation"


class AutomationManager:
    """Validate, compile, create, and persist one automation at a time."""

    def __init__(
        self,
        integration_manager: Optional[IntegrationManager] = None,
        n8n_client: Optional[N8nClient] = None,
        state_store: Optional[IntegrationStateStore] = None,
        compiler: Optional[WorkflowCompiler] = None,
        validator: Optional[WorkflowValidator] = None,
    ):
        self.integration_manager = integration_manager or IntegrationManager()
        self.n8n_client = n8n_client or self.integration_manager.n8n_client
        self.state_store = state_store or self.integration_manager._state_store
        self.validator = validator or WorkflowValidator()
        self.compiler = compiler or WorkflowCompiler(self.integration_manager, self.validator)

    def validate_for_creation(self, organization_id: str, workflow: dict) -> dict:
        try:
            self.validator.validate(workflow)
        except WorkflowCompilationError as exc:
            raise AutomationCreationError(exc.code, exc.message) from exc

        step_integrations = {
            get_tool(step["tool"])["integration"]
            for step in workflow.get("steps", [])
            if get_tool(step.get("tool")) and get_tool(step.get("tool")).get("integration")
        }
        trigger = workflow.get("trigger", {})
        trigger_tool_name = trigger.get("tool")
        trigger_integrations = set()
        if trigger_tool_name:
            t_def = get_tool(trigger_tool_name)
            if t_def and t_def.get("integration") and t_def["integration"] not in ("webhook", "schedule"):
                trigger_integrations.add(t_def["integration"])
        integrations = sorted(step_integrations | trigger_integrations)

        for integration in integrations:
            try:
                self.integration_manager.resolve_credential_reference(
                    organization_id, integration
                )
            except Exception as exc:
                raise AutomationCreationError(
                    "MISSING_INTEGRATION",
                    f"Integration '{integration}' is not connected",
                ) from exc
        return workflow

    def create_automation(self, organization_id: str, workflow: dict) -> dict:
        self.validate_for_creation(organization_id, workflow)
        client = self.n8n_client or self.integration_manager.n8n_client
        if client is None:
            raise AutomationCreationError("N8N_UNAVAILABLE", "n8n is not configured")

        try:
            compiled = self.compiler.compile(workflow, organization_id)
            n8n_payload = {
                k: v for k, v in compiled.items()
                if k not in ("active", "credential_references")
            }
            response = client.create_workflow(n8n_payload)
        except WorkflowCompilationError as exc:
            raise AutomationCreationError(exc.code, exc.message) from exc
        except N8nError as exc:
            raise AutomationCreationError(exc.code, str(exc)) from exc
        except Exception as exc:
            raise AutomationCreationError("N8N_CREATE_FAILED", "n8n workflow creation failed") from exc

        n8n_workflow_id = response.get("id") or response.get("workflowId")
        if not n8n_workflow_id:
            raise AutomationCreationError("MALFORMED_RESPONSE", "n8n returned no workflow ID")

        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": f"auto_{uuid4().hex}",
            "organization_id": organization_id,
            "n8n_workflow_id": str(n8n_workflow_id),
            "name": workflow["name"],
            "status": "created",
            "canonical_workflow": deepcopy(workflow),
            "created_at": now,
            "updated_at": now,
        }
        self.state_store.save_automation(record)
        return {
            "status": record["status"],
            "automation_id": record["id"],
            "n8n_workflow_id": record["n8n_workflow_id"],
            "workflow_name": record["name"],
            "message": "Automation created successfully.",
        }

    def delete_automation(self, organization_id: str, automation_id: str) -> dict:
        record = self.state_store.get_automation(organization_id, automation_id)
        if not record:
            raise AutomationNotFoundError(f"Automation '{automation_id}' not found.")

        client = self.n8n_client or getattr(self.integration_manager, "n8n_client", None)
        n8n_wf_id = record.get("n8n_workflow_id")
        if client and n8n_wf_id:
            try:
                client.delete_workflow(str(n8n_wf_id))
            except Exception as exc:
                logger.warning(f"Could not delete n8n workflow {n8n_wf_id}: {exc}")

        deleted = self.state_store.delete_automation(organization_id, automation_id)
        if not deleted:
            raise AutomationNotFoundError(f"Automation '{automation_id}' not found.")

        recorder = getattr(self.state_store, "save_audit_event", None)
        if recorder:
            try:
                recorder(
                    organization_id,
                    "automation_deleted",
                    automation_id=automation_id,
                    workflow_name=record.get("name"),
                    n8n_workflow_id=n8n_wf_id,
                )
            except Exception:
                pass

        return {
            "status": "deleted",
            "automation_id": automation_id,
            "message": "Automation deleted successfully.",
        }

    def confirmation_summary(self, workflow: dict) -> str:
        trigger = workflow.get("trigger", {})
        trigger_tool = trigger.get("tool")
        if trigger_tool:
            tool_def = get_tool(trigger_tool)
            desc = tool_def.get("description", trigger_tool) if tool_def else trigger_tool
            integration = (tool_def.get("integration") or "").capitalize() if tool_def else ""
            trigger_display = f"{integration} — {desc}" if integration else desc
        else:
            trigger_display = trigger.get("type", "webhook")

        actions = []
        for step in workflow.get("steps", []):
            detail = step["tool"]
            parameters = step.get("parameters", {})
            if step["tool"] == "slack.send_message" and parameters.get("channel"):
                detail += f" to {parameters['channel']}"
            elif step["tool"] == "gmail.send" and parameters.get("to"):
                detail += f" to {parameters['to']}"
            actions.append(detail)
        action_lines = "\n".join(
            f"{index}. {tool}" for index, tool in enumerate(actions, start=1)
        )
        return (
            "I'm about to create this automation:\n\n"
            f"Trigger: {trigger_display}\n\n"
            f"Actions:\n{action_lines}\n\n"
            "Create this automation?"
        )

    def apply_modification(self, canonical_workflow: dict, modification: dict) -> dict:
        return apply_modification(canonical_workflow, modification)

    def find_automation(self, organization_id: str, target: str) -> dict:
        if not target or not isinstance(target, str) or not target.strip():
            raise AutomationNotFoundError("Target automation identifier is required")

        automations = self.state_store.list_automations(organization_id)
        target_clean = target.strip()

        # 1. Exact match on automation ID
        for a in automations:
            if a["id"] == target_clean:
                return a

        # 2. Exact match on name (case-insensitive)
        exact_matches = [
            a for a in automations
            if a["name"].strip().lower() == target_clean.lower()
        ]
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(exact_matches) > 1:
            raise AutomationAmbiguousError(
                f"Multiple automations match name '{target_clean}'",
                matches=exact_matches,
            )

        # 3. Substring / fuzzy match on name (case-insensitive)
        fuzzy_matches = [
            a for a in automations
            if target_clean.lower() in a["name"].lower()
        ]
        if len(fuzzy_matches) == 1:
            return fuzzy_matches[0]
        if len(fuzzy_matches) > 1:
            raise AutomationAmbiguousError(
                f"Multiple automations match '{target_clean}'",
                matches=fuzzy_matches,
            )

        raise AutomationNotFoundError(
            f"Automation '{target_clean}' not found for organization '{organization_id}'"
        )

    def update_automation(self, organization_id: str, automation_id: str, workflow: dict) -> dict:
        existing = self.state_store.get_automation(organization_id, automation_id)
        if not existing:
            raise AutomationNotFoundError(
                f"Automation '{automation_id}' not found for organization '{organization_id}'"
            )

        self.validate_for_creation(organization_id, workflow)
        client = self.n8n_client or self.integration_manager.n8n_client
        if client is None:
            raise AutomationCreationError("N8N_UNAVAILABLE", "n8n is not configured")

        try:
            compiled = self.compiler.compile(workflow, organization_id)
            n8n_payload = {
                k: v for k, v in compiled.items()
                if k not in ("active", "credential_references")
            }
            client.update_workflow(existing["n8n_workflow_id"], n8n_payload)
        except WorkflowCompilationError as exc:
            raise AutomationCreationError(exc.code, exc.message) from exc
        except N8nError as exc:
            raise AutomationCreationError(exc.code, str(exc)) from exc
        except Exception as exc:
            raise AutomationCreationError("N8N_UPDATE_FAILED", "n8n workflow update failed") from exc

        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": existing["id"],
            "organization_id": organization_id,
            "n8n_workflow_id": existing["n8n_workflow_id"],
            "name": workflow.get("name", existing["name"]),
            "status": "updated",
            "canonical_workflow": deepcopy(workflow),
            "created_at": existing["created_at"],
            "updated_at": now,
        }
        self.state_store.save_automation(record)
        return {
            "status": record["status"],
            "automation_id": record["id"],
            "n8n_workflow_id": record["n8n_workflow_id"],
            "workflow_name": record["name"],
            "message": "Automation updated successfully.",
        }

    def confirmation_summary_for_modification(
        self, target_automation: dict, modified_workflow: dict, modification: dict
    ) -> str:
        op = (modification.get("operation") or modification.get("action") or "UPDATE").upper()
        name = target_automation.get("name", "Automation")
        auto_id = target_automation.get("id", "")

        action_lines = []
        for index, step in enumerate(modified_workflow.get("steps", []), start=1):
            detail = step.get("tool", "")
            parameters = step.get("parameters", {})
            if detail == "slack.send_message" and parameters.get("channel"):
                detail += f" to {parameters['channel']}"
            elif detail == "gmail.send" and parameters.get("to"):
                detail += f" to {parameters['to']}"
            action_lines.append(f"{index}. {detail}")
        actions_str = "\n".join(action_lines)

        return (
            f"I'm about to modify the automation '{name}' ({auto_id}):\n\n"
            f"Operation: {op}\n\n"
            f"Updated Actions:\n{actions_str}\n\n"
            "Apply this modification?"
        )