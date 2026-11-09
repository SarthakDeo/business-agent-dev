"""
response_generator.py
Converts structured execution results into a natural-language response for the user.
Uses Gemini to generate a concise, friendly summary.
"""
import os
import json
import logging
from dataclasses import dataclass
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

logger = logging.getLogger(__name__)

RESPONSE_SYSTEM_PROMPT = """You are a helpful AI business assistant.
You are given a user's original request and the structured results from executing that request.
Write a concise, friendly, human-readable response that:
- Directly addresses the user's request
- Summarizes what was done and the key results
- Uses plain language (no JSON, no technical jargon)
- Is 2-5 sentences maximum
- If confirmation was required and is pending, tell the user what needs their approval
"""


FALLBACK_MODELS = [
    os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-pro",
]


@dataclass
class ResponseGenerationResult:
    response_text: str
    status: str
    error: str | None = None


def generate_response(
    user_message: str,
    plan: dict,
    execution_results: dict,
    pending_confirmations: list[dict] = None,
) -> str:
    return generate_response_result(
        user_message, plan, execution_results, pending_confirmations
    ).response_text


def generate_response_result(
    user_message: str,
    plan: dict,
    execution_results: dict,
    pending_confirmations: list[dict] = None,
) -> ResponseGenerationResult:
    """
    Generate a natural language response for the user with model fallback.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or genai is None:
        return ResponseGenerationResult(
            _fallback_response(plan, execution_results, pending_confirmations),
            "fallback",
            "Gemini response generation is unavailable",
        )

    client = genai.Client(api_key=api_key)

    summary_prompt = f"""
User request: "{user_message}"

Plan mode: {plan.get('mode')}
Goal: {plan.get('goal')}

Execution results:
{json.dumps(execution_results, indent=2)}

Pending confirmations (steps not yet executed, awaiting user approval):
{json.dumps(pending_confirmations or [], indent=2)}

Write the response now:
"""

    for model_name in FALLBACK_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=summary_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=RESPONSE_SYSTEM_PROMPT,
                    temperature=0.4,
                ),
            )
            return ResponseGenerationResult(response.text.strip(), "success")
        except Exception:
            logger.warning("Response model %s failed; trying fallback", model_name)
            continue

    return ResponseGenerationResult(
        _fallback_response(plan, execution_results, pending_confirmations),
        "fallback",
        "Gemini response generation failed",
    )


def _fallback_response(plan: dict, results: dict, pending: list) -> str:
    """Simple fallback if Gemini is unavailable."""
    mode = plan.get("mode", "unknown")
    goal = plan.get("goal", "your request")
    
    if pending:
        tools = [p.get("tool", "action") for p in pending]
        if mode == "AUTOMATE":
            return f"I'll create this automation with: {', '.join(tools)}. Please confirm if you want me to proceed."
        return f"This will perform: {', '.join(tools)}. Please confirm if you want me to proceed."
    
    completed = len(results)
    return f"Done! Completed {completed} step(s) for: {goal}."
