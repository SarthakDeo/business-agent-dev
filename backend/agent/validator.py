"""
validator.py
Validates tool call parameters against the Tool Registry input schemas.
"""
import logging
import re
from jsonschema import validate, ValidationError as JsonSchemaValidationError
from .tool_registry import get_tool, tool_exists, is_trigger_tool

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    def __init__(self, step_id: str, tool_name: str, message: str):
        self.step_id = step_id
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"[{step_id}][{tool_name}] Validation failed: {message}")


def _reject_unknown_parameters(parameters: dict, schema: dict, step_id: str, tool_name: str):
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    unknown = set(parameters) - set(properties)
    if unknown:
        field = sorted(unknown)[0]
        raise ValidationError(step_id, tool_name, f"Unexpected parameter '{field}'")
    for key, value in parameters.items():
        property_schema = properties.get(key, {})
        if isinstance(value, dict):
            _reject_unknown_parameters(value, property_schema, step_id, tool_name)
        elif isinstance(value, list):
            item_schema = property_schema.get("items", {})
            for item in value:
                if isinstance(item, dict):
                    _reject_unknown_parameters(item, item_schema, step_id, tool_name)


def validate_agent_plan(plan: dict) -> dict:
    """Validate the top-level structure before tool selection or execution."""
    if not isinstance(plan, dict):
        raise ValidationError("plan", "unknown", "Plan must be an object")
    if plan.get("mode") not in ("CHAT", "ASK", "DO", "AUTOMATE"):
        raise ValidationError("plan", "unknown", "Invalid plan mode")
    if not isinstance(plan.get("goal"), str) or not plan["goal"].strip():
        raise ValidationError("plan", "unknown", "Plan goal must be a non-empty string")
    forbidden_context_fields = {"organization_id", "org_id", "user_id", "permissions", "credential_id"}
    supplied_context_fields = forbidden_context_fields.intersection(plan)
    if supplied_context_fields:
        raise ValidationError("plan", "unknown", "Plan cannot supply runtime security context")

    if plan.get("mode") == "CHAT" or plan.get("clarification_needed"):
        plan.setdefault("steps", [])
        return plan

    is_modify = plan.get("mode") == "AUTOMATE" and plan.get("operation") == "MODIFY"
    if is_modify:
        if not plan.get("target_automation"):
            raise ValidationError("plan", "unknown", "AUTOMATE MODIFY requires target_automation")
        if not isinstance(plan.get("modification"), dict):
            raise ValidationError("plan", "unknown", "AUTOMATE MODIFY requires modification object")
        return plan

    # Validate trigger for AUTOMATE CREATE plans
    if plan.get("mode") == "AUTOMATE":
        trigger = plan.get("trigger")
        if trigger is None and plan.get("automation_config"):
            config = plan["automation_config"]
            trigger = {
                "type": config.get("trigger_type", "webhook"),
                "parameters": config.get("trigger_config") or {},
            }
            plan["trigger"] = trigger

        if not isinstance(trigger, dict):
            raise ValidationError("plan", "unknown", "AUTOMATE requires a trigger object")
        trigger_tool = trigger.get("tool")
        if trigger_tool:
            if not tool_exists(trigger_tool):
                raise ValidationError("trigger", trigger_tool, f"Trigger tool '{trigger_tool}' is not registered")
            if not is_trigger_tool(trigger_tool):
                raise ValidationError("trigger", trigger_tool, f"Action tool '{trigger_tool}' cannot be used as a trigger")
            tool_def = get_tool(trigger_tool)
            trigger_params = trigger.get("parameters", {})
            if not isinstance(trigger_params, dict):
                raise ValidationError("trigger", trigger_tool, "Trigger parameters must be an object")
            if tool_def and "input_schema" in tool_def:
                input_schema = tool_def["input_schema"]
                if trigger_tool != "webhook.received" and trigger.get("type") != "webhook":
                    _reject_unknown_parameters(trigger_params, input_schema, "trigger", trigger_tool)
                try:
                    validate(instance=trigger_params, schema=input_schema)
                except JsonSchemaValidationError as e:
                    raise ValidationError("trigger", trigger_tool, e.message) from e

    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValidationError("plan", "unknown", "Plan steps must be a non-empty list")
    seen_ids = set()
    for step in steps:
        if not isinstance(step, dict):
            raise ValidationError("plan", "unknown", "Each step must be an object")
        step_id = step.get("id")
        valid_automation_id = (
            plan.get("mode") == "AUTOMATE"
            and isinstance(step_id, str)
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", step_id)
        )
        if not isinstance(step_id, str) or (not step_id.startswith("step_") and not valid_automation_id):
            raise ValidationError(str(step_id or "unknown"), "unknown", "Invalid step id")
        if step_id in seen_ids:
            raise ValidationError(step_id, "unknown", "Duplicate step id")
        seen_ids.add(step_id)
        if not isinstance(step.get("tool"), str) or not step["tool"]:
            raise ValidationError(step_id, "unknown", "Step tool must be a string")
        if not tool_exists(step["tool"]):
            raise ValidationError(step_id, step["tool"], "Tool is not registered")
        if is_trigger_tool(step["tool"]):
            raise ValidationError(step_id, step["tool"], f"Trigger tool '{step['tool']}' cannot be used as an action step")
        if not isinstance(step.get("parameters", {}), dict):
            raise ValidationError(step_id, step.get("tool", "unknown"), "Parameters must be an object")
    return plan


def validate_plan(plan: dict) -> dict:
    """
    Validate all steps in the plan against their tool input schemas.
    Template references like {{step_1.field}} are skipped (resolved at runtime).
    
    Returns:
        The same plan dict (unchanged) if all valid.
    
    Raises:
        ValidationError: On first schema violation found.
    """
    for step in plan.get("steps", []):
        step_id = step.get("id", "unknown")
        tool_name = step.get("tool", "unknown")
        parameters = step.get("parameters", {})

        tool_def = get_tool(tool_name)
        if not tool_def:
            raise ValidationError(step_id, tool_name, f"Tool '{tool_name}' not in registry")

        input_schema = tool_def.get("input_schema", {})
        _reject_unknown_parameters(parameters, input_schema, step_id, tool_name)
        
        # Replace template references with typed placeholders for schema validation
        clean_params = _mock_templates_for_validation(parameters, input_schema)
        
        try:
            validate(instance=clean_params, schema=input_schema)
        except JsonSchemaValidationError as e:
            raise ValidationError(step_id, tool_name, e.message) from e
        
        logger.info(f"Validated step {step_id} ({tool_name}) ✓")
    
    return plan


def _mock_templates_for_validation(params: dict, input_schema: dict) -> dict:
    """
    Replace template references ({{step_N.field}}) with typed dummy values
    so schema validation can verify required fields and types.
    """
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
            elif prop_type == "array":
                cleaned[key] = []
            elif prop_type == "object":
                cleaned[key] = {}
            else:
                enums = prop_def.get("enum")
                cleaned[key] = enums[0] if enums else "placeholder"
        elif isinstance(value, list):
            items_def = properties.get(key, {}).get("items", {})
            item_type = items_def.get("type", "string")
            new_list = []
            for v in value:
                if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
                    new_list.append("placeholder" if item_type == "string" else 0)
                else:
                    new_list.append(v)
            cleaned[key] = new_list
        else:
            cleaned[key] = value
    return cleaned
