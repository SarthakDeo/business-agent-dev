"""
execution_manager.py
Coordinates tool execution via n8n webhooks. Resolves templates between steps.
"""
import os
import logging
import requests
from typing import Optional
from .context_manager import ConversationContext
from .tool_registry import get_tool
from ..integrations import dispatch_tool

logger = logging.getLogger(__name__)

N8N_BASE_URL = os.environ.get("N8N_BASE_URL", "http://localhost:5678")
N8N_API_KEY  = os.environ.get("N8N_API_KEY", "")


class ExecutionError(Exception):
    def __init__(self, step_id: str, tool_name: str, message: str):
        self.step_id = step_id
        self.tool_name = tool_name
        super().__init__(f"[{step_id}][{tool_name}] Execution error: {message}")


def execute_plan(
    plan: dict,
    context: ConversationContext,
    agent_run_id: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """
    Execute all steps in the plan sequentially via n8n.
    Steps with requires_confirmation=True must already be approved before calling this.
    
    Args:
        plan: The validated, annotated plan dict.
        context: ConversationContext with step_outputs for template resolution.
        agent_run_id: ID of the current agent run (for audit).
        dry_run: If True, skip actual n8n calls (for testing).
    
    Returns:
        Dict of {step_id: result} for all executed steps.
    """
    results = {}

    for step in plan.get("steps", []):
        step_id = step.get("id")
        tool_name = step.get("tool")
        raw_params = step.get("parameters", {})

        # Resolve template references from prior steps
        resolved_params = context.resolve_templates(raw_params)
        logger.info(f"Executing step {step_id} ({tool_name}) params={resolved_params}")

        if dry_run:
            mock_result = {"success": True, "dry_run": True, "tool": tool_name}
            context.store_step_output(step_id, mock_result)
            results[step_id] = mock_result
            continue

        tool_def = get_tool(tool_name)
        workflow_id = tool_def.get("n8n_workflow_id") if tool_def else None

        try:
            result = _call_n8n(
                workflow_id=workflow_id,
                tool_name=tool_name,
                parameters=resolved_params,
                user_id=context.user_id,
                org_id=context.org_id,
                agent_run_id=agent_run_id,
                step_id=step_id,
            )
        except requests.exceptions.RequestException as net_err:
            logger.warning(f"n8n unreachable ({net_err}). Executing tool '{tool_name}' via native integration handler.")
            result = dispatch_tool(tool_name, resolved_params)
        except Exception as e:
            raise ExecutionError(step_id, tool_name, str(e))

        context.store_step_output(step_id, result)
        results[step_id] = result
        logger.info(f"Step {step_id} completed: success={result.get('success')}")

    return results


def _call_n8n(
    workflow_id: str,
    tool_name: str,
    parameters: dict,
    user_id: str,
    org_id: str,
    agent_run_id: Optional[str],
    step_id: str,
) -> dict:
    """
    POST to the n8n webhook for the given workflow.
    n8n webhooks are at: POST /webhook/{workflow_id}
    """
    if not workflow_id:
        raise ValueError(f"No n8n_workflow_id configured for tool '{tool_name}'")

    url = f"{N8N_BASE_URL}/webhook/{workflow_id}"
    payload = {
        "tool_name": tool_name,
        "parameters": parameters,
        "user_id": user_id,
        "organization_id": org_id,
        "agent_run_id": agent_run_id,
        "step_id": step_id,
    }
    headers = {
        "Content-Type": "application/json",
    }
    if N8N_API_KEY:
        headers["X-N8N-API-KEY"] = N8N_API_KEY

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    
    if resp.status_code not in (200, 201):
        raise ValueError(f"n8n returned HTTP {resp.status_code}: {resp.text}")

    try:
        return resp.json()
    except Exception:
        return {"success": True, "raw": resp.text}
