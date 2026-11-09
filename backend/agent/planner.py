"""
planner.py
Calls Gemini API to convert user request into a structured agent plan (JSON).
Replaces legacy planning engines.
"""
import os
import json
import logging
import re
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from .tool_registry import get_tools_summary_for_prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Voice2FlowPlanner, an AI planning engine for an event-driven business automation agent.

Your job is to analyze the user's business request and produce a structured JSON execution plan.

{tools_summary}

MODES:
- CHAT: Conversational greeting (e.g. "Hello", "How are you"), general questions about Voice2Flow capabilities, or when the user asks for an unsupported capability/integration (such as incoming phone calls, audio calls, SMS) that cannot be executed with the available tools. No tool execution needed.
- ASK: Read-only information query using registered tools. No writes, no side effects.
- DO: One-time immediate action — plan and execute one or more registered action tools (e.g. "Send John an email saying thank you").
- AUTOMATE: Create or modify a persistent recurring or event-driven workflow (e.g. "Reply to each incoming mail by saying thank you for contacting us", "Whenever someone posts in support Slack, notify me", "Every morning at 9, send me a summary").

AUTOMATION vs ONE-TIME ACTION:
- If the user asks for a one-time execution (e.g. "Send an email to John saying thank you", "Check order ORD-123"): Use DO or ASK mode with action steps.
- If the user asks for continuous, recurring, or event-triggered behavior (e.g. "Reply to each incoming mail", "Whenever an email arrives", "For every new message in Slack", "Every morning at 9"): Use AUTOMATE mode with an EVENT TRIGGER.

OUTPUT FORMAT (strict JSON only, no markdown, no explanation):

For CHAT mode (conversational, greetings, or unsupported requests):
{{
  "mode": "CHAT",
  "goal": "<what user said>",
  "response_text": "<helpful conversational response, or polite explanation of what integrations are supported vs unsupported>",
  "steps": [],
  "requires_confirmation": false
}}

For ASK, DO, and AUTOMATE modes:
{{
  "mode": "ASK" | "DO" | "AUTOMATE",
  "goal": "<what the user wants>",
  "requires_confirmation": true | false,
  "name": "<descriptive automation name, e.g. Incoming Email Auto-Reply>", // for AUTOMATE mode
  "operation": "CREATE" | "MODIFY", // for AUTOMATE mode; default "CREATE"
  "target_automation": "<name or ID to modify>", // required for AUTOMATE MODIFY
  "modification": {{ // required for AUTOMATE MODIFY
    "operation": "ADD_STEP" | "REMOVE_STEP" | "REPLACE_STEP" | "UPDATE_PARAMETERS",
    "step_id": "<id of step to remove/replace/update>",
    "step": {{ "id": "...", "tool": "...", "parameters": {{ ... }} }},
    "parameters": {{ ... }}
  }},
  "trigger": {{   // required when mode is AUTOMATE CREATE; must select an EVENT TRIGGER from the list above
    "tool": "<trigger tool name, e.g. gmail.email_received | slack.message_received | schedule.daily | schedule.weekly | webhook.received>",
    "parameters": {{ ... }}
  }},
  "steps": [
    {{
      "id": "step_1",
      "tool": "<action tool name from ACTIONS & QUERIES list>",
      "parameters": {{ ... }},
      "depends_on": [],
      "description": "<what this step does>"
    }}
  ],
  "clarification_needed": false,
  "clarification_question": null
}}

RULES FOR EVENT TRIGGERS & VARIABLES:
1. NEVER use generic webhook triggers for email or Slack events!
   - When the user asks to trigger on incoming emails ("reply to each incoming mail", "when an email arrives", "for every email received", "whenever someone emails us"): MUST use "tool": "gmail.email_received".
   - When the user asks to trigger on incoming Slack messages ("whenever someone posts in #support", "on new Slack message"): MUST use "tool": "slack.message_received".
   - When the user asks to run on a daily or weekly schedule ("every morning at 9", "every day at 8am"): MUST use "tool": "schedule.daily" or "schedule.weekly".
   - Use "webhook.received" ONLY when the user explicitly requests an incoming HTTP webhook or webhook URL endpoint.
2. In step parameters, reference trigger output fields using {{{{trigger.<field>}}}} namespace syntax:
   - For gmail.email_received: {{{{trigger.from}}}} (sender email), {{{{trigger.subject}}}}, {{{{trigger.body}}}}, {{{{trigger.message_id}}}}, {{{{trigger.thread_id}}}}.
     Example for auto-reply:
       "to": "{{{{trigger.from}}}}",
       "subject": "Re: {{{{trigger.subject}}}}",
       "body": "Thank you for contacting us.",
       "thread_id": "{{{{trigger.thread_id}}}}"
   - For slack.message_received: {{{{trigger.channel}}}}, {{{{trigger.text}}}}, {{{{trigger.user}}}}, {{{{trigger.ts}}}}.
   - NEVER use bare {{{{subject}}}}, {{{{from}}}}, or {{{{body}}}}. Always qualify with {{{{trigger.field}}}}.
3. Reference outputs from previous steps using {{{{step_N.field}}}} syntax.
4. Triggers (e.g. gmail.email_received) must ONLY appear in the "trigger" object and NEVER as a step.
5. Actions (e.g. gmail.send, crm.create_ticket) must ONLY appear in the "steps" array and NEVER as a trigger.
6. Ambiguous requests: If the user says "When a customer contacts us..." without specifying whether to watch Gmail, Slack, or website form, set clarification_needed=true and clarification_question="Where should I watch for new customer messages — Gmail, Slack, or your website form?".
7. Unsupported triggers: If the user asks for incoming phone calls, audio calls, or SMS triggers, set mode="CHAT" and explain that phone-call triggers are not supported, and mention supported triggers (Gmail, Slack, schedules).
8. Set requires_confirmation=true for any medium-risk tool or workflow creation/modification.
9. Output ONLY valid JSON. No markdown backticks. No explanation outside JSON.
"""

FALLBACK_MODELS = [
    os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
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

    if plan["mode"] not in ("CHAT", "ASK", "DO", "AUTOMATE"):
        raise ValueError(f"Invalid plan mode: {plan['mode']}")

    if plan.get("mode") == "CHAT" or plan.get("clarification_needed"):
        plan.setdefault("steps", [])
        return

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
            if isinstance(trigger, dict):
                # Ensure trigger has parameters dict
                if not isinstance(trigger.get("parameters"), dict):
                    trigger["parameters"] = {}
                # Support legacy plans with type="webhook"
                if trigger.get("type") == "webhook" and not trigger.get("tool"):
                    trigger["tool"] = "webhook.received"
                elif trigger.get("tool") and not trigger.get("type"):
                    trigger["type"] = trigger["tool"].split(".")[0]
        elif operation == "MODIFY":
            if not plan.get("target_automation"):
                raise ValueError("AUTOMATE MODIFY requires target_automation")
            if not isinstance(plan.get("modification"), dict):
                raise ValueError("AUTOMATE MODIFY requires modification object")
            if "steps" not in plan:
                plan["steps"] = []

    if not isinstance(plan.get("steps"), list):
        raise ValueError("Plan 'steps' must be a list")
