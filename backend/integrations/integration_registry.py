"""Canonical metadata for supported external integrations."""

INTEGRATIONS = {
    "gmail": {
        "id": "gmail",
        "name": "Gmail",
        "auth_type": "oauth2",
        "status": "supported",
    },
    "slack": {
        "id": "slack",
        "name": "Slack",
        "auth_type": "oauth2",
        "status": "supported",
    },
    "crm": {
        "id": "crm",
        "name": "CRM",
        "auth_type": "api_key",
        "status": "supported",
    },
}


def list_supported_integrations() -> list[dict]:
    return [dict(item) for item in INTEGRATIONS.values()]


def get_integration(integration: str) -> dict:
    try:
        return dict(INTEGRATIONS[integration])
    except KeyError as exc:
        raise ValueError(f"Unsupported integration: {integration}") from exc
