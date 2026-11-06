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
from .validator import validate_plan, ValidationError
from .permission_manager import check_permissions, PermissionDeniedError
from .confirmation_manager import evaluate_confirmation, HighRiskBlockedError
from .execution_manager import execute_plan, ExecutionError
from .response_generator import generate_response
from .context_manager import ConversationContext

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
    ):
        self.response_text = response_text
        self.mode = mode
        self.plan = plan
        self.execution_results = execution_results
        self.pending_confirmations = pending_confirmations
        self.status = status      # completed | awaiting_confirmation | error | blocked
        self.run_id = run_id
        self.error = error

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

    def run(
        self,
        user_message: str,
        context: ConversationContext,
        user_permissions: list[str],
        dry_run: bool = False,
    ) -> AgentResponse:
        run_id = str(uuid.uuid4())
        context.run_id = run_id
        context.add_user_message(user_message)
        logger.info(f"[run={run_id}] Processing: '{user_message}'")

        # ── 1. PLAN ──────────────────────────────────────────────
        try:
            agent_plan = plan(user_message, context.get_gemini_history()[:-1])
        except Exception as e:
            logger.error(f"[run={run_id}] Planning failed: {e}")
            return self._error_response(run_id, str(e), "Planning failed")

        logger.info(f"[run={run_id}] Mode={agent_plan['mode']}, Goal={agent_plan['goal']}")

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

        # ── 2. TOOL SELECTION ─────────────────────────────────────
        try:
            agent_plan = select_and_enrich(agent_plan)
        except ToolSelectionError as e:
            return self._error_response(run_id, str(e), "Invalid tool selected")

        # ── 3. VALIDATE PARAMETERS ───────────────────────────────
        try:
            agent_plan = validate_plan(agent_plan)
        except ValidationError as e:
            return self._error_response(run_id, str(e), "Parameter validation failed")

        # ── 4. PERMISSION CHECK ──────────────────────────────────
        try:
            agent_plan = check_permissions(agent_plan, user_permissions, context.user_id)
        except PermissionDeniedError as e:
            return self._error_response(run_id, str(e), "Permission denied", status="blocked")

        # ── 5. CONFIRMATION EVALUATION ───────────────────────────
        try:
            agent_plan = evaluate_confirmation(agent_plan)
        except HighRiskBlockedError as e:
            return self._error_response(run_id, str(e), "High-risk action blocked", status="blocked")

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
                return self._error_response(run_id, str(e), "Execution failed")

        # ── 7. GENERATE RESPONSE ─────────────────────────────────
        status = "awaiting_confirmation" if pending_steps else "completed"
        response_text = generate_response(
            user_message=user_message,
            plan=agent_plan,
            execution_results=exec_results,
            pending_confirmations=pending_steps,
        )
        context.add_agent_message(response_text)

        logger.info(f"[run={run_id}] Done. Status={status}")
        return AgentResponse(
            response_text=response_text,
            mode=agent_plan["mode"],
            plan=agent_plan,
            execution_results=exec_results,
            pending_confirmations=pending_steps,
            status=status,
            run_id=run_id,
        )

    def _error_response(self, run_id: str, error: str, label: str, status: str = "error") -> AgentResponse:
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
        )
