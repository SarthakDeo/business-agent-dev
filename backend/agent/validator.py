"""
validator.py
Validates tool call parameters against the Tool Registry input schemas.
"""
import logging
from jsonschema import validate, ValidationError as JsonSchemaValidationError
from .tool_registry import get_tool

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    def __init__(self, step_id: str, tool_name: str, message: str):
        self.step_id = step_id
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"[{step_id}][{tool_name}] Validation failed: {message}")


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
