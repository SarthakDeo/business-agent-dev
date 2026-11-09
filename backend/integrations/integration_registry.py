"""Canonical metadata for supported external integrations."""

INTEGRATIONS = {
    "gmail": {
        "id": "gmail",
        "name": "Gmail",
        "auth_type": "oauth2",
        "status": "supported",
        "n8n_node_type": "n8n-nodes-base.gmail",
        "n8n_credential_type": "gmailOAuth2",
        "description": "Send and search emails via Google Gmail.",
    },
    "slack": {
        "id": "slack",
        "name": "Slack",
        "auth_type": "bot_token",
        "status": "supported",
        "n8n_node_type": "n8n-nodes-base.slack",
        "n8n_credential_type": "slackApi",
        "description": "Send messages and notifications to Slack channels.",
    },
    "crm": {
        "id": "crm",
        "name": "CRM",
        "auth_type": "api_key",
        "status": "supported",
        "n8n_node_type": "n8n-nodes-base.httpRequest",
        "n8n_credential_type": "httpHeaderAuth",
        "description": "Voice2Flow Built-in Demo CRM (customers, orders, tickets).",
    },
}


def list_supported_integrations() -> list[dict]:
    return [dict(item) for item in INTEGRATIONS.values()]


def get_integration(integration: str) -> dict:
    try:
        return dict(INTEGRATIONS[integration])
    except KeyError as exc:
        raise ValueError(f"Unsupported integration: {integration}") from exc
