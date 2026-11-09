"""
context_manager.py
Maintains conversation context, step output storage, and template resolution.
"""
import re
import logging
from typing import Any, Optional

from ..integrations import IntegrationManager

logger = logging.getLogger(__name__)


class ConversationContext:
    """
    Holds the state for a single agent run / conversation turn.
    """

    def __init__(
        self,
        user_id: str,
        org_id: str,
        conversation_id: Optional[str] = None,
        integration_manager: Optional[IntegrationManager] = None,
    ):
        self.user_id = user_id
        self.org_id = org_id
        self.conversation_id = conversation_id
        self.message_history: list[dict] = []   # Gemini chat history
        self.step_outputs: dict[str, Any] = {}  # step_id -> result dict
        self.pending_steps: list[dict] = []     # steps awaiting user confirmation
        self.pending_plan: Optional[dict] = None
        self.pending_automation_workflow: Optional[dict] = None
        self.pending_automation_id: Optional[str] = None
        self.pending_mode: Optional[str] = None
        self.approved_step_ids: set[str] = set()
        # The context carries infrastructure dependencies for the run.  Callers
        # may inject a shared manager, but a run is never silently unbound.
        self.integration_manager = integration_manager or IntegrationManager()
        self.run_id: Optional[str] = None

    def add_user_message(self, text: str):
        self.message_history.append({"role": "user", "parts": [text]})

    def add_agent_message(self, text: str):
        self.message_history.append({"role": "model", "parts": [text]})

    def store_step_output(self, step_id: str, output: dict):
        self.step_outputs[step_id] = output
        logger.debug("Stored output for %s", step_id)

    def resolve_templates(self, parameters: dict) -> dict:
        """
        Replace {{step_N.field}} references in parameters with actual step outputs.
        Supports dot-notation for nested access: {{step_1.orders[0].customer_id}}
        """
        resolved = {}
        for key, value in parameters.items():
            if isinstance(value, str):
                resolved[key] = self._resolve_string(value)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_string(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                resolved[key] = value
        return resolved

    def _resolve_string(self, value: str) -> Any:
        pattern = r"\{\{([\w.\[\]]+)\}\}"
        match = re.fullmatch(pattern, value.strip())
        if match:
            return self._get_nested(match.group(1))
        # Partial substitution in string
        def replacer(m):
            result = self._get_nested(m.group(1))
            return str(result) if result is not None else m.group(0)
        return re.sub(pattern, replacer, value)

    def _get_nested(self, path: str) -> Any:
        """Navigate step_outputs using dot-path like step_1.orders"""
        parts = re.split(r"\.|\[(\d+)\]", path)
        parts = [p for p in parts if p is not None and p != ""]
        
        current = self.step_outputs
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (IndexError, ValueError):
                    return None
            else:
                return None
        return current

    def get_gemini_history(self) -> list[dict]:
        return self.message_history
