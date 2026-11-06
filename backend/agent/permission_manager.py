"""
permission_manager.py
Checks user/org permissions before tool execution.
"""
import logging
from typing import Optional
from .tool_registry import get_tool

logger = logging.getLogger(__name__)


class PermissionDeniedError(Exception):
    def __init__(self, step_id: str, tool_name: str, required: str, user_id: str):
        self.step_id = step_id
        self.tool_name = tool_name
        self.required_permission = required
        self.user_id = user_id
        super().__init__(
            f"[{step_id}] User '{user_id}' lacks permission '{required}' for tool '{tool_name}'"
        )


def check_permissions(plan: dict, user_permissions: list[str], user_id: str) -> dict:
    """
    Check that the user holds the required permission for every tool in the plan.
    
    Args:
        plan: The enriched plan dict.
        user_permissions: List of permission scopes the user holds (e.g. ["crm.read", "gmail.send"]).
        user_id: User identifier (for logging/audit).
    
    Returns:
        Plan dict unchanged if all permissions satisfied.
    
    Raises:
        PermissionDeniedError: If any step requires a permission the user doesn't have.
    """
    perm_set = set(user_permissions)
    
    for step in plan.get("steps", []):
        step_id = step.get("id", "unknown")
        tool_name = step.get("tool", "unknown")
        
        tool_def = get_tool(tool_name)
        if not tool_def:
            continue
        
        required = tool_def.get("required_permission")
        if required and required not in perm_set:
            logger.warning(
                f"Permission denied: user={user_id}, step={step_id}, "
                f"tool={tool_name}, required={required}"
            )
            raise PermissionDeniedError(step_id, tool_name, required, user_id)
        
        logger.info(f"Permission OK: {tool_name} requires '{required}' — user has it")
    
    return plan
