"""
tool_registry.py
Loads and manages the canonical Tool Registry from docs/tool_registry.yaml.
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

def list_tools() -> list[dict]:
    """Return all registered tools as a list."""
    return list(_load_registry().values())

def tool_exists(name: str) -> bool:
    return name in _load_registry()

def get_tools_summary_for_prompt() -> str:
    """
    Returns a concise text summary of all tools suitable for injecting into a Gemini prompt.
    Format: tool_name | description | risk_level | required_permission | input fields
    """
    lines = ["Available tools (name | description | risk | permission | required_inputs):"]
    for t in list_tools():
        req = t.get("input_schema", {}).get("required", [])
        props = list(t.get("input_schema", {}).get("properties", {}).keys())
        lines.append(
            f"  - {t['name']} | {t['description']} | risk={t['risk_level']} "
            f"| perm={t['required_permission']} | inputs={props} | required={req}"
        )
    return "\n".join(lines)
