"""Validate and deterministically compile canonical Voice2Flow workflows."""

from copy import deepcopy
import re
from typing import Optional

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_schema

from ..integrations import IntegrationManager
from .tool_registry import get_tool, is_trigger_tool, tool_exists


class WorkflowCompilationError(Exception):
    """Safe structured error raised when a workflow cannot be compiled."""

    def __init__(self, message: str, code: str = "COMPILATION_FAILED"):
        self.code = code
        self.message = message
        super().__init__(message)


class WorkflowValidationError(WorkflowCompilationError):
    """Raised when canonical workflow input is invalid."""


class TriggerNodeMapping:
    def __init__(
        self,
        node_type: str,
        credential_key: Optional[str] = None,
        event: Optional[str] = None,
        type_version: int = 1,
    ):
        self.node_type = node_type
        self.credential_key = credential_key
        self.event = event
        self.type_version = type_version


TRIGGER_NODE_MAPPINGS = {
    "gmail.email_received": TriggerNodeMapping(
        node_type="n8n-nodes-base.gmailTrigger",
        credential_key="gmailOAuth2",
        event="messageReceived",
        type_version=1,
    ),
    "slack.message_received": TriggerNodeMapping(
        node_type="n8n-nodes-base.slackTrigger",
        credential_key="slackApi",
        event="message",
        type_version=1,
    ),
    "schedule.daily": TriggerNodeMapping(
        node_type="n8n-nodes-base.scheduleTrigger",
        credential_key=None,
        event="schedule",
        type_version=1,
    ),
    "schedule.weekly": TriggerNodeMapping(
        node_type="n8n-nodes-base.scheduleTrigger",
        credential_key=None,
        event="schedule",
        type_version=1,
    ),
    "webhook.received": TriggerNodeMapping(
        node_type="n8n-nodes-base.webhook",
        credential_key=None,
        event="webhook",
        type_version=2,
    ),
}


class WorkflowValidator:
    """Validate the canonical workflow without performing integration I/O."""

    _reference_pattern = re.compile(r"\{\{([^{}]+)\}\}")
    _valid_trigger_types = {"webhook", "event", "schedule"}
    _secret_keys = {
        "secret", "token", "password", "api_key", "apikey", "access_token",
        "credential", "credential_id", "authorization", "headers",
    }

    def validate(self, workflow: dict) -> dict:
        if not isinstance(workflow, dict):
            self._fail("Workflow must be an object", "INVALID_WORKFLOW")
        if workflow.get("mode") != "AUTOMATE":
            self._fail("Canonical workflows must use AUTOMATE mode", "INVALID_WORKFLOW")

        trigger = workflow.get("trigger")
        if not isinstance(trigger, dict):
            self._fail("Exactly one trigger is required", "INVALID_WORKFLOW")

        trigger_tool = trigger.get("tool")
        if trigger_tool:
            if not tool_exists(trigger_tool):
                self._fail(f"Trigger tool '{trigger_tool}' is not registered", "UNKNOWN_TOOL")
            if not is_trigger_tool(trigger_tool):
                self._fail(f"Tool '{trigger_tool}' cannot be used as a trigger", "INVALID_TRIGGER")
            if trigger_tool not in TRIGGER_NODE_MAPPINGS:
                self._fail(f"Trigger tool '{trigger_tool}' is not supported by the compiler", "UNSUPPORTED_TRIGGER")
            tool = get_tool(trigger_tool)
            trigger_params = trigger.get("parameters", {})
            if not isinstance(trigger_params, dict):
                self._fail("Trigger parameters must be an object", "INVALID_PARAMETER")
            self._reject_secret_fields(trigger_params)
            if trigger_tool != "webhook.received" and trigger.get("type") != "webhook":
                self._reject_unknown_parameters(trigger_params, tool.get("input_schema", {}))
            cleaned_params = _mock_templates_for_validation(trigger_params, tool.get("input_schema", {}))
            try:
                validate_schema(instance=cleaned_params, schema=tool.get("input_schema", {}))
            except JsonSchemaValidationError as exc:
                self._fail(f"Trigger: {exc.message}", "INVALID_PARAMETER")
        else:
            if trigger.get("type") not in self._valid_trigger_types:
                self._fail("Unsupported workflow trigger", "INVALID_WORKFLOW")
            if not isinstance(trigger.get("parameters", {}), dict):
                self._fail("Trigger parameters must be an object", "INVALID_PARAMETER")

        steps = workflow.get("steps")
        if not isinstance(steps, list) or not steps:
            self._fail("Workflow steps must be a non-empty list", "INVALID_WORKFLOW")

        step_ids: set[str] = set()
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                self._fail("Each workflow step must be an object", "INVALID_WORKFLOW")
            step_id = step.get("id")
            tool_name = step.get("tool")
            if not isinstance(step_id, str) or not step_id:
                self._fail("Every step requires an ID", "INVALID_WORKFLOW")
            if step_id in step_ids:
                self._fail(f"Duplicate step ID '{step_id}'", "INVALID_WORKFLOW")
            step_ids.add(step_id)
            if not isinstance(tool_name, str) or not tool_name:
                self._fail(f"Step '{step_id}' requires a tool", "UNKNOWN_TOOL")
            tool = get_tool(tool_name)
            if tool is None:
                self._fail(f"Tool '{tool_name}' is not registered", "UNKNOWN_TOOL")
            if is_trigger_tool(tool_name):
                self._fail(f"Trigger tool '{tool_name}' cannot be used as an action step", "INVALID_TOOL")
            if tool_name not in TOOL_NODE_MAPPINGS:
                self._fail(f"Tool '{tool_name}' is not supported by the compiler", "UNSUPPORTED_TOOL")
            integration = tool.get("integration")
            if integration not in _supported_integration_ids():
                self._fail(
                    f"Integration '{integration}' is not supported",
                    "UNSUPPORTED_INTEGRATION",
                )
            parameters = step.get("parameters")
            if not isinstance(parameters, dict):
                self._fail(f"Parameters for '{step_id}' must be an object", "INVALID_PARAMETER")
            self._reject_secret_fields(parameters)
            self._reject_unknown_parameters(parameters, tool.get("input_schema", {}))
            cleaned = _mock_templates_for_validation(parameters, tool.get("input_schema", {}))
            try:
                validate_schema(instance=cleaned, schema=tool.get("input_schema", {}))
            except JsonSchemaValidationError as exc:
                self._fail(f"Step '{step_id}': {exc.message}", "INVALID_PARAMETER")
            self._validate_references(parameters, trigger, steps, index)

        self._reject_secret_fields(trigger.get("parameters", {}))
        self._validate_references(trigger.get("parameters", {}), trigger, steps, len(steps))
        return workflow

    def _validate_references(self, value, trigger, steps, current_index: int) -> None:
        values = value.values() if isinstance(value, dict) else value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, (dict, list)):
                self._validate_references(item, trigger, steps, current_index)
            elif isinstance(item, str):
                references = self._reference_pattern.findall(item)
                if "{{" in item or "}}" in item:
                    if not references or any(item.count("{{") != item.count("}}") for _ in [0]):
                        self._fail("Malformed workflow reference", "INVALID_REFERENCE")
                for reference in references:
                    parts = reference.split(".")
                    source = parts[0]
                    if len(parts) < 2 or not parts[1]:
                        self._fail(f"Invalid reference '{{{{{reference}}}}}'", "INVALID_REFERENCE")
                    if source == "trigger":
                        trigger_tool_name = trigger.get("tool") or ("webhook.received" if trigger.get("type") == "webhook" else None)
                        if trigger_tool_name and trigger_tool_name != "webhook.received" and trigger.get("type") != "webhook":
                            tool_def = get_tool(trigger_tool_name)
                            if tool_def:
                                output_props = tool_def.get("output_schema", {}).get("properties", {})
                                if parts[1] not in output_props:
                                    self._fail(f"Unknown output field '{parts[1]}' on 'trigger'", "UNKNOWN_REFERENCE")
                        continue
                    matching = next((step for step in steps if step.get("id") == source), None)
                    if matching is None:
                        self._fail(f"Unknown reference source '{source}'", "UNKNOWN_REFERENCE")
                    source_index = steps.index(matching)
                    if source_index >= current_index:
                        self._fail(f"Reference '{source}' must target an earlier step", "INVALID_REFERENCE")
                    output_properties = get_tool(matching["tool"]).get("output_schema", {}).get("properties", {})
                    if parts[1] not in output_properties:
                        self._fail(f"Unknown output field '{parts[1]}' on '{source}'", "UNKNOWN_REFERENCE")

    def _reject_secret_fields(self, value) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in self._secret_keys:
                    self._fail("Raw credentials are not allowed in workflows", "MISSING_CREDENTIAL")
                self._reject_secret_fields(child)
        elif isinstance(value, list):
            for child in value:
                self._reject_secret_fields(child)

    def _reject_unknown_parameters(self, parameters: dict, schema: dict) -> None:
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        unknown = set(parameters) - set(properties)
        if unknown:
            self._fail(
                f"Unexpected parameter '{sorted(unknown)[0]}'",
                "INVALID_PARAMETER",
            )
        for key, value in parameters.items():
            property_schema = properties.get(key, {})
            if isinstance(value, dict):
                self._reject_unknown_parameters(value, property_schema)
            elif isinstance(value, list):
                item_schema = property_schema.get("items", {})
                for item in value:
                    if isinstance(item, dict):
                        self._reject_unknown_parameters(item, item_schema)
    @staticmethod
    def _fail(message: str, code: str):
        raise WorkflowValidationError(message, code)


class ToolNodeMapping:
    def __init__(self, node_type: str, credential_key: str, operation: str):
        self.node_type = node_type
        self.credential_key = credential_key
        self.operation = operation


TOOL_NODE_MAPPINGS = {
    "crm.find_customer": ToolNodeMapping("n8n-nodes-base.httpRequest", "httpHeaderAuth", "find_customer"),
    "crm.find_order": ToolNodeMapping("n8n-nodes-base.httpRequest", "httpHeaderAuth", "find_order"),
    "crm.create_ticket": ToolNodeMapping("n8n-nodes-base.httpRequest", "httpHeaderAuth", "create_ticket"),
    "crm.update_customer": ToolNodeMapping("n8n-nodes-base.httpRequest", "httpHeaderAuth", "update_customer"),
    "gmail.search": ToolNodeMapping("n8n-nodes-base.gmail", "gmailOAuth2", "search"),
    "gmail.send": ToolNodeMapping("n8n-nodes-base.gmail", "gmailOAuth2", "send"),
    "slack.send_message": ToolNodeMapping("n8n-nodes-base.slack", "slackApi", "postMessage"),
}


class WorkflowCompiler:
    """Compile canonical workflows into side-effect-free n8n JSON."""

    def __init__(
        self,
        integration_manager: Optional[IntegrationManager] = None,
        validator: Optional[WorkflowValidator] = None,
    ):
        self.integration_manager = integration_manager or IntegrationManager()
        self.validator = validator or WorkflowValidator()

    def compile(self, workflow: dict, organization_id: str) -> dict:
        if not organization_id:
            raise WorkflowCompilationError("Organization is required", "INVALID_WORKFLOW")
        if not isinstance(workflow, dict):
            raise WorkflowValidationError("Workflow must be an object", "INVALID_WORKFLOW")
        # Preserve the Phase 3 compiler contract for internal step-only plans.
        if workflow.get("trigger") is None:
            return self._compile_legacy(workflow, organization_id)

        self.validator.validate(workflow)
        credential_ids = self._resolve_credentials(workflow, organization_id)
        nodes = [self._trigger_node(workflow["trigger"], credential_ids)]
        for step in workflow["steps"]:
            nodes.append(self._step_node(step, credential_ids, workflow["trigger"], workflow["steps"]))

        connections = {}
        for previous, current in zip(nodes, nodes[1:]):
            connections[previous["name"]] = {
                "main": [[{"node": current["name"], "type": "main", "index": 0}]]
            }
        return {
            "name": workflow.get("name", "Voice2Flow automation"),
            "nodes": nodes,
            "connections": connections,
            "settings": {"executionOrder": "v1"},
            "active": False,
            "credential_references": credential_ids,
        }

    def _resolve_credentials(self, workflow: dict, organization_id: str) -> dict[str, str]:
        step_integrations = {
            get_tool(step["tool"])["integration"]
            for step in workflow.get("steps", [])
            if get_tool(step.get("tool")) and get_tool(step.get("tool")).get("integration")
        }
        trigger = workflow.get("trigger", {})
        trigger_tool = trigger.get("tool")
        trigger_integrations = set()
        if trigger_tool and trigger_tool in TRIGGER_NODE_MAPPINGS:
            mapping = TRIGGER_NODE_MAPPINGS[trigger_tool]
            if mapping.credential_key:
                tool_def = get_tool(trigger_tool)
                if tool_def and tool_def.get("integration") and tool_def["integration"] not in ("webhook", "schedule"):
                    trigger_integrations.add(tool_def["integration"])
        integrations = sorted(step_integrations | trigger_integrations)

        references = {}
        for integration in integrations:
            try:
                gnani_reference = self.integration_manager.resolve_integration(
                    organization_id, integration
                )
                provider = self.integration_manager.n8n_credential_provider
                if self.integration_manager.n8n_client is not None:
                    references[integration] = provider.resolve_reference(
                        organization_id, gnani_reference.id
                    ).id
                else:
                    references[integration] = gnani_reference.id
            except Exception as exc:
                raise WorkflowCompilationError(
                    f"Credential for integration '{integration}' is unavailable",
                    "MISSING_CREDENTIAL",
                ) from exc
        return references

    def _trigger_node(self, trigger: dict, credential_ids: Optional[dict[str, str]] = None) -> dict:
        credential_ids = credential_ids or {}
        trigger_tool = trigger.get("tool") or ("webhook.received" if trigger.get("type") == "webhook" else None)
        mapping = TRIGGER_NODE_MAPPINGS.get(trigger_tool, TRIGGER_NODE_MAPPINGS["webhook.received"])
        parameters = deepcopy(trigger.get("parameters", {}))

        node_parameters = {}
        if mapping.node_type == "n8n-nodes-base.webhook":
            path = parameters.get("path", "gnani-webhook")
            node_parameters = {
                "httpMethod": "POST",
                "path": path,
                "responseMode": "lastNode",
            }
        elif mapping.node_type == "n8n-nodes-base.gmailTrigger":
            filters = {}
            read_status = parameters.get("read_status", "unread")
            if read_status:
                filters["readStatus"] = read_status
            if parameters.get("query"):
                filters["q"] = parameters["query"]
            node_parameters = {
                "authentication": "oAuth2",
                "event": "messageReceived",
                "simple": False,
                "filters": filters,
            }
        elif mapping.node_type == "n8n-nodes-base.slackTrigger":
            node_parameters = {
                "event": "message",
            }
            if parameters.get("channel"):
                node_parameters["channel"] = parameters["channel"]
        elif mapping.node_type == "n8n-nodes-base.scheduleTrigger":
            if trigger_tool == "schedule.weekly":
                day = parameters.get("day_of_week", "monday")
                hour = parameters.get("hour", 9)
                minute = parameters.get("minute", 0)
                node_parameters = {
                    "rule": {
                        "interval": [
                            {
                                "field": "weeks",
                                "triggerAtHour": hour,
                                "triggerAtMinute": minute,
                                "triggerAtDay": [day],
                            }
                        ]
                    }
                }
            else:
                hour = parameters.get("hour", 9)
                minute = parameters.get("minute", 0)
                node_parameters = {
                    "rule": {
                        "interval": [
                            {
                                "field": "days",
                                "triggerAtHour": hour,
                                "triggerAtMinute": minute,
                            }
                        ]
                    }
                }
        else:
            node_parameters = parameters

        node = {
            "id": "gnani-trigger",
            "name": "Trigger",
            "type": mapping.node_type,
            "typeVersion": mapping.type_version,
            "position": [240, 300],
            "parameters": node_parameters,
        }
        if mapping.credential_key:
            tool_def = get_tool(trigger_tool) if trigger_tool else None
            integration = tool_def.get("integration") if tool_def else None
            if integration and integration in credential_ids:
                node["credentials"] = {mapping.credential_key: {"id": credential_ids[integration]}}
        return node

    def _step_node(self, step: dict, credential_ids: dict[str, str], trigger: dict, steps: list[dict]) -> dict:
        mapping = TOOL_NODE_MAPPINGS[step["tool"]]
        integration = get_tool(step["tool"])["integration"]
        mapped_input = self._map_parameters(step["parameters"], trigger, steps)
        node_parameters = {
            "operation": mapping.operation,
            "tool": step["tool"],
            "input": mapped_input,
        }
        if step["tool"] == "gmail.send":
            node_parameters["resource"] = "message"
            node_parameters["operation"] = "send"
            node_parameters["toEmail"] = mapped_input.get("to", "")
            node_parameters["subject"] = mapped_input.get("subject", "")
            node_parameters["message"] = mapped_input.get("body", "")
            if mapped_input.get("thread_id"):
                node_parameters.setdefault("options", {})["threadId"] = mapped_input["thread_id"]
            if mapped_input.get("cc"):
                node_parameters.setdefault("options", {})["ccEmail"] = mapped_input["cc"]
        elif step["tool"] == "slack.send_message":
            node_parameters["resource"] = "message"
            node_parameters["operation"] = "post"
            node_parameters["channel"] = mapped_input.get("channel", "")
            node_parameters["text"] = mapped_input.get("message", "")

        return {
            "id": f"gnani-{step['id']}",
            "name": step["id"],
            "type": mapping.node_type,
            "typeVersion": 1,
            "position": [520, 300 + steps.index(step) * 180],
            "parameters": node_parameters,
            "credentials": {mapping.credential_key: {"id": credential_ids[integration]}},
        }

    def _map_parameters(self, parameters: dict, trigger: dict, steps: list[dict]) -> dict:
        return {key: self._map_value(value, trigger, steps) for key, value in parameters.items()}

    def _map_value(self, value, trigger: dict, steps: list[dict]):
        if isinstance(value, dict):
            return {key: self._map_value(child, trigger, steps) for key, child in value.items()}
        if isinstance(value, list):
            return [self._map_value(child, trigger, steps) for child in value]
        if not isinstance(value, str):
            return value
        references = WorkflowValidator._reference_pattern.findall(value)
        if not references:
            return value
        expression_parts = []
        cursor = 0
        for match in WorkflowValidator._reference_pattern.finditer(value):
            literal = value[cursor:match.start()]
            if literal:
                expression_parts.append(repr(literal))
            expression_parts.append(self._n8n_reference(match.group(1)))
            cursor = match.end()
        if cursor < len(value):
            expression_parts.append(repr(value[cursor:]))
        if len(expression_parts) == 1:
            return "={{" + expression_parts[0] + "}}"
        return "={{" + " + ".join(expression_parts) + "}}"

    @staticmethod
    def _n8n_reference(reference: str) -> str:
        source, field = reference.split(".", 1)
        if source == "trigger":
            field_expressions = {
                "from": '($node["Trigger"].json["from"] || $node["Trigger"].json["From"])',
                "to": '($node["Trigger"].json["to"] || $node["Trigger"].json["To"])',
                "subject": '($node["Trigger"].json["subject"] || $node["Trigger"].json["Subject"])',
                "body": '($node["Trigger"].json["text"] || $node["Trigger"].json["body"] || $node["Trigger"].json["snippet"])',
                "message_id": '($node["Trigger"].json["id"] || $node["Trigger"].json["message_id"])',
                "thread_id": '($node["Trigger"].json["threadId"] || $node["Trigger"].json["thread_id"])',
                "date": '($node["Trigger"].json["date"] || $node["Trigger"].json["Date"])',
            }
            if field in field_expressions:
                return field_expressions[field]
            return f'$node["Trigger"].json["{field}"]'
        return f'$node["{source}"].json["{field}"]'

    def _compile_legacy(self, workflow: dict, organization_id: str) -> dict:
        integrations = self._required_integrations(workflow)
        references = {}
        try:
            for integration in integrations:
                references[integration] = self.integration_manager.resolve_integration(
                    organization_id, integration
                ).id
        except Exception as exc:
            raise WorkflowCompilationError(
                f"Integration is not connected for organization '{organization_id}'",
                "MISSING_INTEGRATION",
            ) from exc
        nodes = []
        for index, step in enumerate(workflow.get("steps", []), start=1):
            nodes.append(self._legacy_node(f"step_{index}", step, references))
        return {
            "name": workflow.get("name", "Voice2Flow automation"),
            "active": False,
            "nodes": nodes,
            "credential_references": references,
        }

    def _required_integrations(self, workflow: dict) -> set[str]:
        return {
            get_tool(entry.get("tool"))["integration"]
            for entry in workflow.get("steps", [])
            if get_tool(entry.get("tool")) and get_tool(entry.get("tool")).get("integration")
        }

    @staticmethod
    def _legacy_node(node_id: str, entry: dict, references: dict[str, str]) -> dict:
        tool = get_tool(entry.get("tool"))
        integration = tool.get("integration") if tool else None
        _reject_unsafe_legacy_fields(entry.get("parameters", {}))
        node = {
            "id": node_id,
            "name": entry.get("tool", node_id),
            "type": "n8n-nodes-base.httpRequest",
            "parameters": deepcopy(entry.get("parameters", {})),
        }
        if integration:
            node["credentials"] = {integration: {"id": references[integration]}}
        return node


def _reject_unsafe_legacy_fields(value) -> None:
    forbidden = {
        "nodes", "connections", "credentials", "credential", "credential_id",
        "authorization", "headers", "url", "shell", "code",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in forbidden:
                raise WorkflowCompilationError(
                    f"Unsafe workflow field '{key}' is not allowed",
                    "INVALID_PARAMETER",
                )
            _reject_unsafe_legacy_fields(child)
    elif isinstance(value, list):
        for child in value:
            _reject_unsafe_legacy_fields(child)


def _supported_integration_ids() -> set[str]:
    from ..integrations.integration_registry import list_supported_integrations

    return {item["id"] for item in list_supported_integrations()}


def _mock_templates_for_validation(params: dict, input_schema: dict) -> dict:
    properties = input_schema.get("properties", {})
    cleaned = {}
    for key, value in params.items():
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            prop_def = properties.get(key, {})
            prop_type = prop_def.get("type", "string")
            if prop_type == "integer":
                cleaned[key] = 0
            elif prop_type == "number":
                cleaned[key] = 0.0
            elif prop_type == "boolean":
                cleaned[key] = True
            elif prop_type in ("array", "object"):
                cleaned[key] = [] if prop_type == "array" else {}
            else:
                cleaned[key] = (prop_def.get("enum") or ["placeholder"])[0]
        else:
            cleaned[key] = value
    return cleaned
