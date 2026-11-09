"""
planner.py
Calls Gemini API to convert user request into a structured agent plan (JSON).
Replaces legacy planning engines.
"""
import os
import json
import logging
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from .tool_registry import get_tools_summary_for_prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Voice2FlowPlanner, an AI planning engine for a business automation agent.

Your job is to analyze the user's business request and produce a structured JSON execution plan.

{tools_summary}

MODES:
- ASK: Read-only information query. No writes, no side effects.
- DO: One-time action — plan and execute one or more tools.
- AUTOMATE: Create or modify a persistent recurring/event-driven workflow.

OUTPUT FORMAT (strict JSON only, no markdown, no explanation):
{{
  "mode": "ASK" | "DO" | "AUTOMATE",
  "goal": "<what the user wants>",
  "requires_confirmation": true | false,
  "operation": "CREATE" | "MODIFY", // for AUTOMATE mode; default "CREATE"
  "target_automation": "<name or ID to modify>", // required for AUTOMATE MODIFY
  "modification": {{ // required for AUTOMATE MODIFY
    "operation": "ADD_STEP" | "REMOVE_STEP" | "REPLACE_STEP" | "UPDATE_PARAMETERS",
    "step_id": "<id of step to remove/replace/update>",
    "step": {{ "id": "...", "tool": "...", "parameters": {{ ... }} }},
    "parameters": {{ ... }}
  }},
  "trigger": {{   // required when mode is AUTOMATE CREATE; omit for ASK, DO, and MODIFY
    "type": "webhook",
    "parameters": {{ "path": "customer_complaint" }}
  }},
  "steps": [
    {{
      "id": "step_1",
      "tool": "<tool_name from registry>",
      "parameters": {{ ... }},
      "depends_on": [],
      "description": "<what this step does>"
    }}
  ],
  "clarification_needed": false,
  "clarification_question": null
}}

Rules:
- Only use tools listed in the Available tools section.
- Use {{step_N.field}} syntax to reference outputs from previous steps.
- Set requires_confirmation=true for any medium-risk tool or workflow creation/modification.
- For AUTOMATE CREATE, provide the canonical trigger object with type and parameters, plus a safe human-readable workflow name. Never generate n8n JSON.
- For AUTOMATE MODIFY, specify target_automation and the modification object.
- If you don't know enough to plan, set clarification_needed=true and ask in clarification_question.
- Output ONLY valid JSON. No markdown. No explanation text outside JSON.
"""

FALLBACK_MODELS = [
    os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-pro",
]


def plan(user_message: str, conversation_history: list[dict] = None) -> dict:
    """
    Call Gemini to produce a structured agent plan with multi-model fallback.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")

    client = genai.Client(api_key=api_key)

    tools_summary = get_tools_summary_for_prompt()
    system = SYSTEM_PROMPT.format(tools_summary=tools_summary)

    history = conversation_history or []
    last_err = None

    for model_name in FALLBACK_MODELS:
        try:
            chat = client.chats.create(
                model=model_name,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
                history=history,
            )
            response = chat.send_message(user_message)
            raw = response.text.strip()
            logger.debug("Gemini planner response received from %s", model_name)

            plan_dict = json.loads(raw)
            _validate_plan_structure(plan_dict)
            return plan_dict

        except Exception as e:
            last_err = e
            logger.warning("Model %s failed; trying next fallback", model_name)
            continue

    raise RuntimeError(f"All Gemini models failed: {last_err}") from last_err


def _validate_plan_structure(plan: dict) -> None:
    """Basic structural validation of the plan dict."""
    required_keys = {"mode", "goal"}
    missing = required_keys - set(plan.keys())
    if missing:
        raise ValueError(f"Plan missing required keys: {missing}")

    if plan["mode"] not in ("ASK", "DO", "AUTOMATE"):
        raise ValueError(f"Invalid plan mode: {plan['mode']}")

    if plan["mode"] == "AUTOMATE":
        operation = plan.get("operation", "CREATE")
        if operation not in ("CREATE", "MODIFY"):
            raise ValueError(f"Invalid AUTOMATE operation: {operation}")
        if operation == "CREATE":
            trigger = plan.get("trigger")
            legacy_config = plan.get("automation_config")
            if trigger is None and legacy_config is None:
                raise ValueError("AUTOMATE plans require a canonical trigger")
            if trigger is not None and not isinstance(trigger, dict):
                raise ValueError("AUTOMATE trigger must be an object")
        elif operation == "MODIFY":
            if not plan.get("target_automation"):
                raise ValueError("AUTOMATE MODIFY requires target_automation")
            if not isinstance(plan.get("modification"), dict):
                raise ValueError("AUTOMATE MODIFY requires modification object")
            if "steps" not in plan:
                plan["steps"] = []

    if not isinstance(plan.get("steps"), list):
        raise ValueError("Plan 'steps' must be a list")
