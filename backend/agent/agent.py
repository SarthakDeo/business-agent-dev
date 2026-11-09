"""
agent.py
Main Agent orchestrator — the core product.
Coordinates: Planner → ToolSelector → Validator → PermissionManager →
             ConfirmationManager → ExecutionManager → ResponseGenerator
"""
import logging
import uuid
from typing import Optional

from .planner import plan
from .tool_selector import select_and_enrich, ToolSelectionError
from .tool_registry import get_tool
from .validator import validate_plan, validate_agent_plan, ValidationError
from .permission_manager import check_permissions, PermissionDeniedError
from .confirmation_manager import evaluate_confirmation, HighRiskBlockedError
from .execution_manager import execute_plan, ExecutionError
from .automation_manager import (
    AutomationCreationError,
    AutomationManager,
    AutomationNotFoundError,
    AutomationAmbiguousError,
    InvalidModificationError,
    canonical_workflow_from_plan,
)
from .response_generator import generate_response_result
from .context_manager import ConversationContext
from ..integrations import IntegrationManager

logger = logging.getLogger(__name__)


class AgentResponse:
    def __init__(
        self,
        response_text: str,
        mode: str,
        plan: dict,
        execution_results: dict,
        pending_confirmations: list,
        status: str,
        run_id: str,
        error: Optional[str] = None,
        error_code: Optional[str] = None,
    ):
        self.response_text = response_text
        self.mode = mode
        self.plan = plan
        self.execution_results = execution_results
        self.pending_confirmations = pending_confirmations
        self.status = status      # completed | awaiting_confirmation | error | blocked
        self.run_id = run_id
        self.error = error
        self.error_code = error_code
        self.response_generation_status = "success"

    def to_dict(self) -> dict:
        return {
            "response": self.response_text,
            "mode": self.mode,
            "status": self.status,
            "run_id": self.run_id,
            "plan": self.plan,
            "execution_results": self.execution_results,
            "pending_confirmations": self.pending_confirmations,
            "error": self.error,
            "error_code": self.error_code,
            "response_generation_status": self.response_generation_status,
        }


class Agent:
    """
    The core AI Agent.
    
    Usage:
        ctx = ConversationContext(user_id="u1", org_id="org1")
        agent = Agent()
        result = agent.run("How many delayed orders do we have?", ctx, user_permissions=["crm.read"])
        print(result.response_text)
    """

    def __init__(self, integration_manager: Optional[IntegrationManager] = None):
        self.integration_manager = integration_manager or IntegrationManager()
        self.automation_manager = AutomationManager(self.integration_manager)

    def run(
        self,
        user_message: str,
        context: ConversationContext,
        user_permissions: list[str],
        dry_run: bool = False,
    ) -> AgentResponse:
        run_id = str(uuid.uuid4())
        if getattr(context, "pending_steps", []) and getattr(context, "pending_plan", None):
            pending_mode = getattr(context, "pending_mode", None) or context.pending_plan.get("mode", "unknown")
            if pending_mode.startswith("AUTOMATE"):
                pending_mode = "AUTOMATE"
            return AgentResponse(
                response_text="A confirmation is already pending. Please approve or reject it first.",
                mode=pending_mode,
                plan=context.pending_plan,
                execution_results={},
                pending_confirmations=context.pending_steps,
                status="awaiting_confirmation",
                run_id=context.run_id or run_id,
                error_code="CONFIRMATION_REQUIRED",
            )
        if context.integration_manager is None:
            context.integration_manager = self.integration_manager
        context.run_id = run_id
        context.add_user_message(user_message)
        try:
            self._audit(context, "AGENT_REQUEST", mode=None, status="received", metadata={"message_length": len(user_message)})
        except Exception:
            return self._error_response(
                run_id, "Persistence is unavailable", "Request could not be recorded",
                error_code="DATABASE_UNAVAILABLE",
            )
        logger.info(f"[run={run_id}] Processing: '{user_message}'")

        # ── 1. PLAN ──────────────────────────────────────────────
        try:
            agent_plan = plan(user_message, context.get_gemini_history()[:-1])
            validate_agent_plan(agent_plan)
        except Exception as e:
            logger.error(f"[run={run_id}] Planning failed: {e}")
            return self._error_response(run_id, str(e), "Planning failed")

        logger.info(f"[run={run_id}] Mode={agent_plan['mode']}, Goal={agent_plan['goal']}")
        try:
            self._audit(
                context,
                "PLAN_CREATED",
                mode=agent_plan.get("mode"),
                status="validated",
                metadata={"step_count": len(agent_plan.get("steps", []))},
            )
        except Exception:
            return self._error_response(
                run_id, "Persistence is unavailable", "Plan could not be recorded",
                error_code="DATABASE_UNAVAILABLE",
            )

        # If Gemini needs clarification
        if agent_plan.get("clarification_needed"):
            question = agent_plan.get("clarification_question", "Could you clarify your request?")
            context.add_agent_message(question)
            return AgentResponse(
                response_text=question,
                mode=agent_plan["mode"],
                plan=agent_plan,
                execution_results={},
                pending_confirmations=[],
                status="clarification_needed",
                run_id=run_id,
            )

        mode = agent_plan.get("mode")
        if mode == "CHAT":
            return self._handle_chat(run_id, agent_plan, context)
        if mode == "ASK":
            return self._handle_ask(run_id, user_message, agent_plan, context, user_permissions, dry_run)
        if mode == "DO":
            return self._handle_do(run_id, user_message, agent_plan, context, user_permissions, dry_run)
        if mode == "AUTOMATE":
            return self._handle_automate(run_id, agent_plan, context, user_permissions)
        return self._error_response(
            run_id, "Unsupported request mode", "Invalid mode", error_code="INVALID_MODE"
        )

    def _handle_chat(
        self, run_id: str, agent_plan: dict, context: ConversationContext
    ) -> AgentResponse:
        response_text = (
            agent_plan.get("response_text")
            or agent_plan.get("goal")
            or "Hello! How can I help you today?"
        )
        context.add_agent_message(response_text)
        try:
            self._audit(
                context,
                "AGENT_RESPONSE",
                mode="CHAT",
                status="completed",
                metadata={"response_length": len(response_text)},
            )
        except Exception:
            return self._error_response(
                run_id, "Persistence is unavailable", "Response could not be recorded",
                error_code="DATABASE_UNAVAILABLE",
            )
        return AgentResponse(
            response_text=response_text,
            mode="CHAT",
            plan=agent_plan,
            execution_results={},
            pending_confirmations=[],
            status="completed",
            run_id=run_id,
        )

    def _handle_ask(
        self, run_id: str, user_message: str, agent_plan: dict, context: ConversationContext,
        user_permissions: list[str], dry_run: bool,
    ) -> AgentResponse:
        for step in agent_plan.get("steps", []):
            tool = get_tool(step.get("tool"))
            if tool is not None and tool.get("risk_level") != "low":
                return self._error_response(
                    run_id,
                    "ASK requests may only use read-only tools",
                    "Invalid ASK operation",
                    error_code="INVALID_MODE",
                )
        return self._handle_tool_mode(run_id, user_message, agent_plan, context, user_permissions, dry_run)

    def _handle_do(
        self, run_id: str, user_message: str, agent_plan: dict, context: ConversationContext,
        user_permissions: list[str], dry_run: bool,
    ) -> AgentResponse:
        return self._handle_tool_mode(run_id, user_message, agent_plan, context, user_permissions, dry_run)

    def _handle_tool_mode(
        self, run_id: str, user_message: str, agent_plan: dict, context: ConversationContext,
        user_permissions: list[str], dry_run: bool,
    ) -> AgentResponse:
        """Shared ASK/DO path; AUTOMATE never enters one-time execution."""
        # ── 2. TOOL SELECTION ─────────────────────────────────────
        try:
            agent_plan = select_and_enrich(agent_plan)
        except ToolSelectionError as e:
            return self._error_response(run_id, str(e), "Invalid tool selected", error_code="TOOL_NOT_FOUND")

        # ── 3. VALIDATE PARAMETERS ───────────────────────────────
        try:
            agent_plan = validate_plan(agent_plan)
        except ValidationError as e:
            return self._error_response(run_id, str(e), "Parameter validation failed", error_code="INVALID_PARAMETERS")

        # ── 4. PERMISSION CHECK ──────────────────────────────────
        try:
            agent_plan = check_permissions(agent_plan, user_permissions, context.user_id)
        except PermissionDeniedError as e:
            return self._error_response(run_id, str(e), "Permission denied", status="blocked", error_code="PERMISSION_DENIED")

        # ── 5. CONFIRMATION EVALUATION ───────────────────────────
        try:
            agent_plan = evaluate_confirmation(agent_plan)
        except HighRiskBlockedError as e:
            return self._error_response(run_id, str(e), "High-risk action blocked", status="blocked", error_code="PERMISSION_DENIED")

        # ── 6. SPLIT: immediate vs. pending confirmation ──────────
        immediate_steps = []
        pending_steps = []
        for step in agent_plan.get("steps", []):
            if step.get("requires_confirmation"):
                pending_steps.append(step)
            else:
                immediate_steps.append(step)

        # Execute immediate (low-risk) steps now
        exec_results = {}
        if immediate_steps:
            immediate_plan = {**agent_plan, "steps": immediate_steps}
            try:
                exec_results = execute_plan(immediate_plan, context, run_id, dry_run=dry_run)
            except ExecutionError as e:
                return self._error_response(run_id, str(e), "Execution failed", error_code="EXECUTION_FAILED")

        # ── 7. GENERATE RESPONSE ─────────────────────────────────
        status = "awaiting_confirmation" if pending_steps else "completed"
        context.pending_steps = pending_steps
        context.pending_plan = agent_plan
        context.pending_mode = agent_plan.get("mode") if pending_steps else None

        response_result = generate_response_result(
            user_message=user_message,
            plan=agent_plan,
            execution_results=exec_results,
            pending_confirmations=pending_steps,
        )
        response_text = response_result.response_text
        context.add_agent_message(response_text)

        logger.info(f"[run={run_id}] Done. Status={status}")
        result = AgentResponse(
            response_text=response_text,
            mode=agent_plan["mode"],
            plan=agent_plan,
            execution_results=exec_results,
            pending_confirmations=pending_steps,
            status=status,
            run_id=run_id,
        )
        result.response_generation_status = response_result.status
        return result

    def resume_confirmation(
        self,
        context: ConversationContext,
        approved: bool,
        dry_run: bool = False,
    ) -> AgentResponse:
        """
        Resume execution of pending steps after the user confirms or rejects.
        """
        run_id = context.run_id or str(uuid.uuid4())
        pending_steps = getattr(context, "pending_steps", [])
        pending_plan = getattr(context, "pending_plan", {}) or {}
        pending_mode = getattr(context, "pending_mode", None) or pending_plan.get("mode", "DO")

        if not pending_steps:
            return AgentResponse(
                response_text="No pending actions found awaiting confirmation.",
                mode=pending_mode,
                plan=pending_plan,
                execution_results={},
                pending_confirmations=[],
                status="completed",
                run_id=run_id,
            )

        if not approved:
            context.pending_steps = []
            context.pending_plan = None
            context.pending_automation_workflow = None
            context.pending_automation_id = None
            context.pending_mode = None
            cancelled_msg = "The pending action was cancelled by the user."
            context.add_agent_message(cancelled_msg)
            return AgentResponse(
                response_text=cancelled_msg,
                mode=pending_plan.get("mode", "DO"),
                plan=pending_plan,
                execution_results={},
                pending_confirmations=[],
                status="cancelled",
                run_id=run_id,
                error_code="CONFIRMATION_REJECTED",
            )

        if pending_mode == "AUTOMATE_MODIFY":
            workflow = getattr(context, "pending_automation_workflow", None)
            automation_id = getattr(context, "pending_automation_id", None)
            try:
                automation_manager = self._automation_manager_for(context)
                automation_result = automation_manager.update_automation(
                    context.org_id, automation_id, workflow
                )
            except (AutomationCreationError, AutomationNotFoundError) as exc:
                return self._error_response(
                    run_id,
                    f"{getattr(exc, 'code', 'ERROR')}: {getattr(exc, 'message', str(exc))}",
                    "Automation update failed",
                    error_code="AUTOMATION_UPDATE_FAILED",
                )

            context.pending_steps = []
            context.pending_plan = None
            context.pending_automation_workflow = None
            context.pending_automation_id = None
            context.pending_mode = None
            workflow_name = automation_result["workflow_name"]
            workflow_id = automation_result["n8n_workflow_id"]
            return AgentResponse(
                response_text=(
                    f"Automation '{workflow_name}' updated successfully. "
                    f"Automation ID: {automation_id}. "
                    f"n8n Workflow ID: {workflow_id}."
                ),
                mode="AUTOMATE",
                plan=pending_plan,
                execution_results={"automation": automation_result},
                pending_confirmations=[],
                status="completed",
                run_id=run_id,
            )

        if pending_mode == "AUTOMATE":
            workflow = getattr(context, "pending_automation_workflow", None)
            try:
                if workflow is None:
                    workflow = canonical_workflow_from_plan(pending_plan)
                automation_manager = self._automation_manager_for(context)
                automation_result = automation_manager.create_automation(
                    context.org_id, workflow
                )
            except AutomationCreationError as exc:
                return self._error_response(
                    run_id,
                    f"{exc.code}: {exc.message}",
                    "Automation creation failed",
                    error_code="AUTOMATION_CREATION_FAILED",
                )

            context.pending_steps = []
            context.pending_plan = None
            context.pending_automation_workflow = None
            context.pending_automation_id = None
            context.pending_mode = None
            automation_id = automation_result["automation_id"]
            workflow_id = automation_result["n8n_workflow_id"]
            return AgentResponse(
                response_text=(
                    "Automation created successfully. "
                    f"Automation ID: {automation_id}. "
                    f"n8n Workflow ID: {workflow_id}."
                ),
                mode="AUTOMATE",
                plan=pending_plan,
                execution_results={"automation": automation_result},
                pending_confirmations=[],
                status="completed",
                run_id=run_id,
            )

        # Approved: execute the pending steps
        try:
            exec_plan = {**pending_plan, "steps": pending_steps}
            context.approved_step_ids = {step.get("id") for step in pending_steps}
            new_results = execute_plan(exec_plan, context, run_id, dry_run=dry_run)
        except ExecutionError as e:
            return self._error_response(run_id, str(e), "Execution of approved steps failed", error_code="EXECUTION_FAILED")

        context.pending_steps = []
        context.pending_plan = None
        context.pending_mode = None
        context.approved_step_ids = set()

        goal = pending_plan.get("goal", "execute approved steps")
        response_result = generate_response_result(
            user_message=f"Action confirmed by user: {goal}",
            plan=pending_plan,
            execution_results=new_results,
            pending_confirmations=[],
        )
        response_text = response_result.response_text
        context.add_agent_message(response_text)

        result = AgentResponse(
            response_text=response_text,
            mode=pending_plan.get("mode", "DO"),
            plan=pending_plan,
            execution_results=new_results,
            pending_confirmations=[],
            status="completed",
            run_id=run_id,
        )
        result.response_generation_status = response_result.status
        return result

    def _handle_automate(
        self,
        run_id: str,
        agent_plan: dict,
        context: ConversationContext,
        user_permissions: list[str],
    ) -> AgentResponse:
        """Prepare and hold an automation until the existing confirmation resumes it."""
        operation = agent_plan.get("operation", "CREATE")
        if operation == "MODIFY":
            return self._handle_automate_modify(
                run_id, agent_plan, context, user_permissions
            )

        try:
            selected_plan = select_and_enrich(agent_plan)
            selected_plan = validate_plan(selected_plan)
            selected_plan = check_permissions(
                selected_plan, user_permissions, context.user_id
            )
            selected_plan = evaluate_confirmation(selected_plan)
            workflow = canonical_workflow_from_plan(selected_plan)
            automation_manager = self._automation_manager_for(context)
            automation_manager.validate_for_creation(context.org_id, workflow)
        except (ToolSelectionError, ValidationError, PermissionDeniedError,
                HighRiskBlockedError, AutomationCreationError) as exc:
            return self._error_response(
                run_id, str(exc), "Automation planning failed",
                error_code="AUTOMATION_CREATION_FAILED",
            )

        context.pending_steps = selected_plan.get("steps", [])
        context.pending_plan = selected_plan
        context.pending_automation_workflow = workflow
        context.pending_mode = "AUTOMATE"
        summary = automation_manager.confirmation_summary(workflow)
        context.add_agent_message(summary)
        return AgentResponse(
            response_text=summary,
            mode="AUTOMATE",
            plan=selected_plan,
            execution_results={},
            pending_confirmations=context.pending_steps,
            status="awaiting_confirmation",
            run_id=run_id,
        )

    def _handle_automate_modify(
        self,
        run_id: str,
        agent_plan: dict,
        context: ConversationContext,
        user_permissions: list[str],
    ) -> AgentResponse:
        automation_manager = self._automation_manager_for(context)
        target = agent_plan.get("target_automation")
        try:
            target_record = automation_manager.find_automation(context.org_id, target)
        except AutomationNotFoundError as exc:
            return self._error_response(
                run_id, str(exc), "Automation not found", error_code="AUTOMATION_NOT_FOUND"
            )
        except AutomationAmbiguousError as exc:
            return self._error_response(
                run_id, str(exc), "Multiple automations matched", error_code="AUTOMATION_AMBIGUOUS"
            )

        modification = agent_plan.get("modification", {})
        try:
            modified_workflow = automation_manager.apply_modification(
                target_record["canonical_workflow"], modification
            )
        except InvalidModificationError as exc:
            return self._error_response(
                run_id, str(exc), "Invalid modification", error_code="INVALID_MODIFICATION"
            )

        try:
            automation_manager.validate_for_creation(context.org_id, modified_workflow)
        except AutomationCreationError as exc:
            return self._error_response(
                run_id, str(exc), "Automation validation failed", error_code=exc.code
            )

        try:
            check_permissions(modified_workflow, user_permissions, context.user_id)
        except PermissionDeniedError as exc:
            context.pending_steps = []
            context.pending_plan = None
            context.pending_automation_workflow = None
            context.pending_automation_id = None
            context.pending_mode = None
            return self._error_response(
                run_id, str(exc), "Permission denied", status="blocked", error_code="PERMISSION_DENIED"
            )

        try:
            evaluate_confirmation(modified_workflow)
        except HighRiskBlockedError as exc:
            context.pending_steps = []
            context.pending_plan = None
            context.pending_automation_workflow = None
            context.pending_automation_id = None
            context.pending_mode = None
            return self._error_response(
                run_id, str(exc), "Risk classification failed", status="blocked",
                error_code="PERMISSION_DENIED",
            )

        context.pending_steps = modified_workflow.get("steps", [])
        context.pending_plan = agent_plan
        context.pending_automation_workflow = modified_workflow
        context.pending_automation_id = target_record["id"]
        context.pending_mode = "AUTOMATE_MODIFY"

        summary = automation_manager.confirmation_summary_for_modification(
            target_record, modified_workflow, modification
        )
        context.add_agent_message(summary)
        return AgentResponse(
            response_text=summary,
            mode="AUTOMATE",
            plan=agent_plan,
            execution_results={},
            pending_confirmations=context.pending_steps,
            status="awaiting_confirmation",
            run_id=run_id,
        )

    def _automation_manager_for(self, context: ConversationContext) -> AutomationManager:
        if context.integration_manager is self.integration_manager:
            return self.automation_manager
        return AutomationManager(
            integration_manager=context.integration_manager,
            n8n_client=getattr(context.integration_manager, "n8n_client", None),
        )

    def _error_response(
        self, run_id: str, error: str, label: str, status: str = "error",
        error_code: Optional[str] = None,
    ) -> AgentResponse:
        logger.error(f"[run={run_id}] {label}: {error}")
        return AgentResponse(
            response_text=f"Sorry, I encountered an issue: {label}. Please try again.",
            mode="unknown",
            plan={},
            execution_results={},
            pending_confirmations=[],
            status=status,
            run_id=run_id,
            error=error,
            error_code=error_code or "PLANNING_FAILED",
        )

    @staticmethod
    def _audit(context: ConversationContext, event_type: str, **event) -> None:
        store = getattr(getattr(context, "integration_manager", None), "_state_store", None)
        recorder = getattr(store, "save_audit_event", None)
        if recorder is None:
            return
        recorder(
            context.org_id,
            event_type,
            user_id=context.user_id,
            request_id=context.run_id,
            run_id=context.run_id,
            **event,
        )
