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
from .confirmation_manager import RISK_CONFIRMATION_REQUIRED
from ..integrations import IntegrationManager, dispatch_tool
from ..integrations import N8nClient, N8nConfig, N8nCredentialError, N8nError

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
    integration_manager: Optional[IntegrationManager] = None,
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
        logger.info(f"Executing step {step_id} ({tool_name})")

        tool_def = get_tool(tool_name)
        if not tool_def:
            raise ExecutionError(step_id, tool_name, "Tool is not registered")
        if (
            tool_def.get("risk_level") in RISK_CONFIRMATION_REQUIRED
            and step_id not in getattr(context, "approved_step_ids", set())
        ):
            results[step_id] = {
                "success": False,
                "error_code": "CONFIRMATION_REQUIRED",
                "error_message": "Tool execution requires user confirmation",
                "tool": tool_name,
            }
            continue
        workflow_id = tool_def.get("n8n_workflow_id") if tool_def else None
        if dry_run:
            mock_result = {"success": True, "dry_run": True, "tool": tool_name}
            context.store_step_output(step_id, mock_result)
            results[step_id] = mock_result
            continue

        credential_reference = None
        manager = integration_manager or getattr(context, "integration_manager", None)
        try:
            if manager is None:
                raise LookupError("Integration manager is not configured")
            integration = tool_def.get("integration")
            credential_reference = manager.resolve_credential_reference(
                context.org_id, integration
            ).id
        except Exception as exc:
            raise ExecutionError(step_id, tool_name, "Integration is not connected") from exc

        try:
            n8n_client = getattr(manager, "n8n_client", None)
            n8n_credential_id = None
            if n8n_client is not None:
                n8n_reference = manager.n8n_credential_provider.resolve_reference(
                    context.org_id, credential_reference
                )
                n8n_credential_id = n8n_reference.id
            result = _call_n8n(
                workflow_id=workflow_id,
                tool_name=tool_name,
                parameters=resolved_params,
                user_id=context.user_id,
                org_id=context.org_id,
                agent_run_id=agent_run_id,
                step_id=step_id,
                credential_reference=credential_reference,
                n8n_client=n8n_client,
                n8n_credential_id=n8n_credential_id,
            )
        except requests.exceptions.RequestException as net_err:
            logger.warning(f"n8n unreachable. Executing tool '{tool_name}' via native integration handler.")
            result = dispatch_tool(
                tool_name,
                resolved_params,
                organization_id=context.org_id,
                credential_reference=credential_reference,
            )
        except N8nError as n8n_error:
            if n8n_error.code == "CONNECTION_FAILED" or n8n_client is None:
                logger.warning(f"n8n unreachable. Executing tool '{tool_name}' via native integration handler.")
                result = dispatch_tool(
                    tool_name,
                    resolved_params,
                    organization_id=context.org_id,
                    credential_reference=credential_reference,
                )
            else:
                raise ExecutionError(step_id, tool_name, n8n_error.args[0]) from n8n_error
        except N8nCredentialError as credential_error:
            raise ExecutionError(step_id, tool_name, str(credential_error)) from credential_error
        except Exception:
            raise ExecutionError(step_id, tool_name, "Integration execution failed")

        if isinstance(result, dict) and result.get("success") is False:
            raise ExecutionError(
                step_id,
                tool_name,
                result.get("error_message", "Tool execution failed"),
            )
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
    credential_reference: str | None = None,
    n8n_client: N8nClient | None = None,
    n8n_credential_id: str | None = None,
) -> dict:
    """
    POST to the n8n webhook for the given workflow.
    n8n webhooks are at: POST /webhook/{workflow_id}
    """
    if not workflow_id:
        raise ValueError(f"No n8n_workflow_id configured for tool '{tool_name}'")

    payload = {
        "tool_name": tool_name,
        "parameters": parameters,
        "user_id": user_id,
        "organization_id": org_id,
        "agent_run_id": agent_run_id,
        "step_id": step_id,
        "credential_reference": credential_reference,
    }
    if n8n_credential_id:
        payload["credential_id"] = n8n_credential_id
    client = n8n_client or N8nClient(N8nConfig(N8N_BASE_URL, N8N_API_KEY))
    if n8n_client is not None:
        return client.execute_workflow(workflow_id, payload)
    return client.invoke_webhook(workflow_id, payload)
