"""
tool_selector.py
Maps planned steps to registered tools and enriches them with tool metadata.
"""
import logging
from .tool_registry import get_tool, tool_exists

logger = logging.getLogger(__name__)


class ToolSelectionError(Exception):
    pass


def select_and_enrich(plan: dict) -> dict:
    """
    Validate every step's tool name against the Tool Registry.
    Attach full tool definition to each step.
    
    Returns:
        Updated plan dict with enriched steps.
    
    Raises:
        ToolSelectionError: If any step references an unregistered tool.
    """
    enriched_steps = []
    for step in plan.get("steps", []):
        tool_name = step.get("tool")
        if not tool_name:
            raise ToolSelectionError(f"Step {step.get('id')} has no tool name")
        
        if not tool_exists(tool_name):
            raise ToolSelectionError(
                f"Step {step.get('id')} references unregistered tool: '{tool_name}'. "
                f"Only tools in the Tool Registry are allowed."
            )
        
        tool_def = get_tool(tool_name)
        enriched_steps.append({
            **step,
            "_tool_def": tool_def,  # attach full definition
        })
        logger.info(f"Tool selected: {tool_name} (risk={tool_def['risk_level']})")
    
    return {**plan, "steps": enriched_steps}
