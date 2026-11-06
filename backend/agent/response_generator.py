"""
response_generator.py
Converts structured execution results into a natural-language response for the user.
Uses Gemini to generate a concise, friendly summary.
"""
import os
import json
import logging
import google.generativeai as genai

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


def generate_response(
    user_message: str,
    plan: dict,
    execution_results: dict,
    pending_confirmations: list[dict] = None,
) -> str:
    """
    Generate a natural language response for the user with model fallback.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return _fallback_response(plan, execution_results, pending_confirmations)

    genai.configure(api_key=api_key)

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
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=RESPONSE_SYSTEM_PROMPT,
                generation_config=genai.GenerationConfig(temperature=0.4),
            )
            response = model.generate_content(summary_prompt)
            return response.text.strip()
        except Exception as e:
            logger.warning(f"Response model {model_name} failed: {e}. Trying fallback...")
            continue

    return _fallback_response(plan, execution_results, pending_confirmations)


def _fallback_response(plan: dict, results: dict, pending: list) -> str:
    """Simple fallback if Gemini is unavailable."""
    mode = plan.get("mode", "unknown")
    goal = plan.get("goal", "your request")
    
    if pending:
        tools = [p.get("tool", "action") for p in pending]
        return f"I've planned to {goal}. The following actions need your approval: {', '.join(tools)}."
    
    completed = len(results)
    return f"Done! Completed {completed} step(s) for: {goal}."
