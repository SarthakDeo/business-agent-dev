"""
confirmation_manager.py
Determines which plan steps require explicit user confirmation before execution.
"""
import logging
from .tool_registry import get_tool

logger = logging.getLogger(__name__)

RISK_CONFIRMATION_REQUIRED = {"medium", "high"}
RISK_BLOCK = {"high"}
RISK_LEVELS = {"low", "medium", "high"}


class HighRiskBlockedError(Exception):
    def __init__(self, step_id: str, tool_name: str):
        super().__init__(
            f"[{step_id}] Tool '{tool_name}' is HIGH RISK and cannot be executed without elevation."
        )


def evaluate_confirmation(plan: dict) -> dict:
    """
    Annotate each step with whether it needs user confirmation.
    Block high-risk steps outright.
    
    Returns:
        Plan dict with each step annotated with:
        - 'requires_confirmation': bool
        - 'risk_level': str
    
    Raises:
        HighRiskBlockedError: If any step involves a high-risk tool.
    """
    any_confirmation_needed = False
    annotated_steps = []

    for step in plan.get("steps", []):
        step_id = step.get("id", "unknown")
        tool_name = step.get("tool", "unknown")
        
        tool_def = get_tool(tool_name)
        if not tool_def or tool_def.get("risk_level") not in RISK_LEVELS:
            raise HighRiskBlockedError(step_id, tool_name)
        risk = tool_def["risk_level"]

        if risk in RISK_BLOCK:
            raise HighRiskBlockedError(step_id, tool_name)

        needs_confirmation = risk in RISK_CONFIRMATION_REQUIRED

        if needs_confirmation:
            any_confirmation_needed = True
            logger.info(f"Step {step_id} ({tool_name}) requires confirmation (risk={risk})")

        annotated_steps.append({
            **step,
            "requires_confirmation": needs_confirmation,
            "risk_level": risk,
        })

    return {
        **plan,
        "steps": annotated_steps,
        "requires_confirmation": any_confirmation_needed,
    }
