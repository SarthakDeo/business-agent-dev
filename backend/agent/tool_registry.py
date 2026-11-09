"""
tool_registry.py
Loads and manages the canonical Tool Registry from docs/tool_registry.yaml.
Explicitly distinguishes between event triggers (workflow starters) and actions/queries (step operations).
"""
import os
import yaml
from pathlib import Path
from typing import Optional

# Singleton cache
_registry: dict = {}

def _load_registry() -> dict:
    global _registry
    if _registry:
        return _registry
    yaml_path = Path(__file__).resolve().parents[2] / "docs" / "tool_registry.yaml"
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    _registry = {tool["name"]: tool for tool in data.get("tools", [])}
    return _registry

def get_tool(name: str) -> Optional[dict]:
    """Return a single tool definition by name, or None if not found."""
    return _load_registry().get(name)

def list_tools(include_triggers: bool = False) -> list[dict]:
    """Return registered action/step tools (or all tools if include_triggers=True)."""
    tools = list(_load_registry().values())
    if not include_triggers:
        return [t for t in tools if t.get("kind") != "trigger"]
    return tools

def list_all_tools() -> list[dict]:
    """Return all registered tools including triggers."""
    return list(_load_registry().values())

def tool_exists(name: str) -> bool:
    return name in _load_registry()

def get_tool_kind(name: str) -> str:
    """Return the capability kind: 'trigger', 'action', or 'query'."""
    tool = get_tool(name)
    if not tool:
        return "unknown"
    return tool.get("kind", "action")

def is_trigger_tool(name: str) -> bool:
    """Check if the tool is an event or schedule trigger."""
    return get_tool_kind(name) == "trigger"

def is_action_tool(name: str) -> bool:
    """Check if the tool is an action or query step."""
    kind = get_tool_kind(name)
    return kind in ("action", "query")

def list_trigger_tools() -> list[dict]:
    """Return all registered trigger tools."""
    return [t for t in list_all_tools() if t.get("kind") == "trigger"]

def list_action_tools() -> list[dict]:
    """Return all registered action and query tools."""
    return [t for t in list_all_tools() if t.get("kind") != "trigger"]

def get_tools_summary_for_prompt() -> str:
    """
    Returns a structured text summary of all tools suitable for injecting into a Gemini prompt.
    Explicitly groups triggers separately from actions so the planner understands workflow starters.
    """
    triggers = list_trigger_tools()
    actions = list_action_tools()

    lines = [
        "EVENT TRIGGERS (use ONLY as 'trigger': {'tool': '<name>', ...} to start AUTOMATE workflows):"
    ]
    for t in triggers:
        inputs = list(t.get("input_schema", {}).get("properties", {}).keys())
        outputs = list(t.get("output_schema", {}).get("properties", {}).keys())
        out_refs = [f"{{{{trigger.{o}}}}}" for o in outputs]
        lines.append(
            f"  - {t['name']} | {t['description']} | event={t.get('event')} "
            f"| inputs={inputs} | outputs={out_refs}"
        )

    lines.append("")
    lines.append(
        "ACTIONS & QUERIES (use ONLY in plan 'steps' for ASK, DO, and AUTOMATE modes):"
    )
    for t in actions:
        req = t.get("input_schema", {}).get("required", [])
        props = list(t.get("input_schema", {}).get("properties", {}).keys())
        lines.append(
            f"  - {t['name']} | {t['description']} | risk={t.get('risk_level', 'low')} "
            f"| perm={t.get('required_permission')} | inputs={props} | required={req}"
        )

    return "\n".join(lines)
