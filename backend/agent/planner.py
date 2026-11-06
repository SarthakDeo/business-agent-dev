"""
planner.py
Calls Gemini API to convert user request into a structured agent plan (JSON).
Replaces Gnani Evon.
"""
import os
import json
import logging
from typing import Optional
import google.generativeai as genai
from .tool_registry import get_tools_summary_for_prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are GnaniPlanner, an AI planning engine for a business automation agent.

Your job is to analyze the user's business request and produce a structured JSON execution plan.

{tools_summary}

MODES:
- ASK: Read-only information query. No writes, no side effects.
- DO: One-time action — plan and execute one or more tools.
- AUTOMATE: Create a persistent recurring/event-driven workflow.

OUTPUT FORMAT (strict JSON only, no markdown, no explanation):
{{
  "mode": "ASK" | "DO" | "AUTOMATE",
  "goal": "<what the user wants>",
  "requires_confirmation": true | false,
  "steps": [
    {{
      "id": "step_1",
      "tool": "<tool_name from registry>",
      "parameters": {{ ... }},
      "depends_on": [],
      "description": "<what this step does>"
    }}
  ],
  "automation_config": {{   // only when mode is AUTOMATE
    "trigger_type": "schedule" | "event" | "webhook",
    "trigger_config": {{ "cron": "0 */6 * * *" }},
    "name": "<automation name>"
  }},
  "clarification_needed": false,
  "clarification_question": null
}}

Rules:
- Only use tools listed in the Available tools section.
- Use {{step_N.field}} syntax to reference outputs from previous steps.
- Set requires_confirmation=true for any medium-risk tool.
- If you don't know enough to plan, set clarification_needed=true and ask in clarification_question.
- Output ONLY valid JSON. No markdown. No explanation text outside JSON.
"""

def plan(user_message: str, conversation_history: list[dict] = None) -> dict:
    """
    Call Gemini to produce a structured agent plan.
    
    Args:
        user_message: The user's natural language request.
        conversation_history: List of prior messages [{"role": "user"|"model", "parts": ["text"]}]
    
    Returns:
        Parsed plan dict matching the agent JSON schema.
    
    Raises:
        ValueError: If Gemini returns invalid JSON or unknown mode.
        RuntimeError: If Gemini API call fails.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")

    genai.configure(api_key=api_key)

    tools_summary = get_tools_summary_for_prompt()
    system = SYSTEM_PROMPT.format(tools_summary=tools_summary)

    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    model = genai.GenerativeModel(
        model_name=gemini_model,
        system_instruction=system,
        generation_config=genai.GenerationConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    history = conversation_history or []
    chat = model.start_chat(history=history)

    try:
        response = chat.send_message(user_message)
        raw = response.text.strip()
        logger.debug(f"Gemini raw response: {raw}")
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e}") from e

    try:
        plan_dict = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON: {raw}")
        raise ValueError(f"Gemini returned invalid JSON: {e}") from e

    _validate_plan_structure(plan_dict)
    return plan_dict


def _validate_plan_structure(plan: dict) -> None:
    """Basic structural validation of the plan dict."""
    required_keys = {"mode", "goal", "steps"}
    missing = required_keys - set(plan.keys())
    if missing:
        raise ValueError(f"Plan missing required keys: {missing}")

    if plan["mode"] not in ("ASK", "DO", "AUTOMATE"):
        raise ValueError(f"Invalid plan mode: {plan['mode']}")

    if not isinstance(plan.get("steps"), list):
        raise ValueError("Plan 'steps' must be a list")
