"""
tests/test_credential_architecture.py
Verification suite for Voice2Flow provider-specific credential architecture:
- Gmail (Google OAuth 2.0 -> n8n gmailOAuth2)
- Slack (Bot User OAuth Token -> n8n slackApi)
- Built-in CRM (Internal API Key -> n8n httpHeaderAuth)
- Tenant isolation and opaque reference resolution in WorkflowCompiler
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from backend.agent.workflow_compiler import WorkflowCompiler
from backend.integrations.connection_manager import IntegrationManager
from backend.integrations.integration_registry import get_integration, list_supported_integrations
from backend.integrations.n8n_client import N8nClient, N8nConfig
from backend.integrations.n8n_credentials import N8nCredentialProvider
from backend.integrations.oauth_service import (
    create_oauth_state,
    get_google_auth_url,
    verify_and_consume_oauth_state,
)


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


def n8n_client_with(*responses):
    session = FakeSession(responses)
    return N8nClient(N8nConfig("http://n8n.test", "fake-api-key"), session), session


# ─── 1. INTEGRATION REGISTRY AUDIT ───────────────────────────────────────────

def test_integration_registry_metadata():
    """Supported integrations must have explicit provider-specific authentication types."""
    supported = {i["id"]: i for i in list_supported_integrations()}

    assert "gmail" in supported
    assert supported["gmail"]["auth_type"] == "oauth2"
    assert supported["gmail"]["n8n_credential_type"] == "gmailOAuth2"
    assert supported["gmail"]["n8n_node_type"] == "n8n-nodes-base.gmail"

    assert "slack" in supported
    assert supported["slack"]["auth_type"] == "bot_token"
    assert supported["slack"]["n8n_credential_type"] == "slackApi"
    assert supported["slack"]["n8n_node_type"] == "n8n-nodes-base.slack"

    assert "crm" in supported
    assert supported["crm"]["auth_type"] == "api_key"
    assert supported["crm"]["n8n_credential_type"] == "httpHeaderAuth"
    assert supported["crm"]["n8n_node_type"] == "n8n-nodes-base.httpRequest"


# ─── 2. GMAIL OAUTH STATE & PROVISIONING ──────────────────────────────────────

def test_gmail_oauth_csrf_state_lifecycle():
    """OAuth CSRF state must be single-use, scoped, and expirable."""
    state = create_oauth_state("org-test", user_id="user-1")
    assert state and len(state) >= 32

    # Wrong tenant must be rejected
    rejected = verify_and_consume_oauth_state(state, organization_id="other-org")
    assert rejected is None

    # Correct tenant must succeed on first try
    info = verify_and_consume_oauth_state(state, organization_id="org-test")
    assert info is not None
    assert info["organization_id"] == "org-test"
    assert info["user_id"] == "user-1"

    # Single-use: second attempt with same state must fail
    second_try = verify_and_consume_oauth_state(state, organization_id="org-test")
    assert second_try is None


def test_gmail_oauth_url_generation():
    """get_google_auth_url must construct valid URL with Gmail scopes."""
    with patch("backend.integrations.oauth_service.get_google_client_id", return_value="mock-client-id.apps.googleusercontent.com"):
        url, state = get_google_auth_url("org-alpha", user_id="user-1")
        assert "accounts.google.com/o/oauth2/v2/auth" in url
        assert "client_id=mock-client-id.apps.googleusercontent.com" in url
        assert "gmail.readonly" in url
        assert "gmail.send" in url
        assert f"state={state}" in url


def test_gmail_n8n_credential_provisioning_with_token_json():
    """Gmail tokens must be provisioned to n8n as gmailOAuth2 with oauthTokenData."""
    client, session = n8n_client_with(FakeResponse(data={"id": "n8n-gmail-cred-1"}))
    provider = N8nCredentialProvider()

    token_payload = json.dumps({
        "access_token": "ya29.mock_access_token",
        "refresh_token": "1//mock_refresh_token",
        "expires_in": 3600,
        "token_type": "Bearer",
    })

    with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "client-id-123", "GOOGLE_CLIENT_SECRET": "client-secret-456"}):
        reference = provider.provision("org-test", "gmail", token_payload, client=client)

    assert reference.id == "n8n-gmail-cred-1"
    assert reference.integration == "gmail"

    call = session.calls[0]
    payload = call[2]["json"]
    assert payload["type"] == "gmailOAuth2"
    assert payload["name"] == "voice2flow-org-test-gmail"
    assert "oauthTokenData" in payload["data"]
    assert payload["data"]["oauthTokenData"]["access_token"] == "ya29.mock_access_token"
    assert payload["data"]["oauthTokenData"]["refresh_token"] == "1//mock_refresh_token"
    assert payload["data"]["clientId"] == "client-id-123"
    assert payload["data"]["clientSecret"] == "client-secret-456"


# ─── 3. SLACK BOT TOKEN & PROVISIONING ────────────────────────────────────────

def test_slack_n8n_credential_provisioning():
    """Slack bot token must be provisioned to n8n as slackApi with accessToken."""
    client, session = n8n_client_with(FakeResponse(data={"id": "n8n-slack-cred-1"}))
    provider = N8nCredentialProvider()

    bot_token = "xoxb-123456789-abcdefg"
    reference = provider.provision("org-test", "slack", bot_token, client=client)

    assert reference.id == "n8n-slack-cred-1"
    assert reference.integration == "slack"

    call = session.calls[0]
    payload = call[2]["json"]
    assert payload["type"] == "slackApi"
    assert payload["name"] == "voice2flow-org-test-slack"
    assert payload["data"]["accessToken"] == bot_token


# ─── 4. BUILT-IN CRM HTTP HEADER AUTH & PROVISIONING ──────────────────────────

def test_crm_n8n_credential_provisioning():
    """CRM demo key must be provisioned to n8n as httpHeaderAuth with X-API-Key."""
    client, session = n8n_client_with(FakeResponse(data={"id": "n8n-crm-cred-1"}))
    provider = N8nCredentialProvider()

    api_key = "demo-crm-api-key-999"
    reference = provider.provision("org-test", "crm", api_key, client=client)

    assert reference.id == "n8n-crm-cred-1"
    assert reference.integration == "crm"

    call = session.calls[0]
    payload = call[2]["json"]
    assert payload["type"] == "httpHeaderAuth"
    assert payload["name"] == "voice2flow-org-test-crm"
    assert payload["data"]["name"] == "X-API-Key"
    assert payload["data"]["value"] == api_key


# ─── 5. WORKFLOW COMPILER CREDENTIAL RESOLUTION & OPAQUE MAPPINGS ─────────────

def test_workflow_compiler_maps_all_three_integrations_correctly():
    """Workflow compiler must map Gmail, Slack, and CRM to their exact n8n node types and credentials."""
    client, _ = n8n_client_with(
        FakeResponse(data={"id": "n8n-crm-id"}),
        FakeResponse(data={"id": "n8n-gmail-id"}),
        FakeResponse(data={"id": "n8n-slack-id"}),
    )
    provider = N8nCredentialProvider()
    manager = IntegrationManager(n8n_client=client, n8n_credential_provider=provider)

    manager.connect("org-x", "crm", "crm-secret", account_identifier="CRM Admin")
    manager.connect("org-x", "gmail", json.dumps({"access_token": "token-1"}), account_identifier="user@gmail.com")
    manager.connect("org-x", "slack", "xoxb-token-1", account_identifier="#alerts")

    workflow = {
        "mode": "AUTOMATE",
        "name": "Multi-Provider Flow",
        "trigger": {"type": "webhook", "parameters": {"path": "test-webhook"}},
        "steps": [
            {
                "id": "step_crm",
                "tool": "crm.find_customer",
                "parameters": {"customer_id": "CUST-001"},
            },
            {
                "id": "step_gmail",
                "tool": "gmail.send",
                "parameters": {"to": "customer@example.com", "subject": "Hello", "body": "Body"},
            },
            {
                "id": "step_slack",
                "tool": "slack.send_message",
                "parameters": {"channel": "#general", "message": "Email sent"},
            },
        ],
    }

    compiler = WorkflowCompiler(manager)
    compiled = compiler.compile(workflow, "org-x")

    # Step 1: CRM -> n8n-nodes-base.httpRequest with httpHeaderAuth
    crm_node = next(n for n in compiled["nodes"] if n["id"] == "gnani-step_crm")
    assert crm_node["type"] == "n8n-nodes-base.httpRequest"
    assert "httpHeaderAuth" in crm_node["credentials"]
    assert crm_node["credentials"]["httpHeaderAuth"]["id"] == "n8n-crm-id"

    # Step 2: Gmail -> n8n-nodes-base.gmail with gmailOAuth2
    gmail_node = next(n for n in compiled["nodes"] if n["id"] == "gnani-step_gmail")
    assert gmail_node["type"] == "n8n-nodes-base.gmail"
    assert "gmailOAuth2" in gmail_node["credentials"]
    assert gmail_node["credentials"]["gmailOAuth2"]["id"] == "n8n-gmail-id"

    # Step 3: Slack -> n8n-nodes-base.slack with slackApi
    slack_node = next(n for n in compiled["nodes"] if n["id"] == "gnani-step_slack")
    assert slack_node["type"] == "n8n-nodes-base.slack"
    assert "slackApi" in slack_node["credentials"]
    assert slack_node["credentials"]["slackApi"]["id"] == "n8n-slack-id"

    # Raw secrets or tokens must NEVER appear in the compiled workflow
    compiled_str = json.dumps(compiled)
    assert "crm-secret" not in compiled_str
    assert "token-1" not in compiled_str
    assert "xoxb-token-1" not in compiled_str


def test_tenant_isolation_in_compiler():
    """Org A's connected credentials cannot compile workflows for Org B."""
    manager = IntegrationManager()
    manager.connect("org-a", "slack", "xoxb-token-org-a")

    compiler = WorkflowCompiler(manager)
    workflow = {
        "mode": "AUTOMATE",
        "name": "Org B Flow",
        "trigger": {"type": "webhook", "parameters": {"path": "b-hook"}},
        "steps": [
            {
                "id": "step_1",
                "tool": "slack.send_message",
                "parameters": {"channel": "#general", "message": "hello"},
            }
        ],
    }

    # Org A compiles fine
    res_a = compiler.compile(workflow, "org-a")
    assert res_a is not None

    # Org B must be rejected because slack is not connected for Org B
    with pytest.raises(Exception, match="unavailable"):
        compiler.compile(workflow, "org-b")


# ─── 6. GMAIL OAUTH API ROUTE HANDLERS ────────────────────────────────────────

def test_gmail_oauth_url_endpoint_when_unconfigured():
    """Endpoint must raise 400 when Google OAuth is not configured in env."""
    from fastapi import HTTPException
    from backend.api.dependencies import TenantContext
    from backend.api.routes.integrations import get_gmail_oauth_url_endpoint

    tenant = TenantContext(organization_id="org-test", user_id="user-1")

    with patch("backend.api.routes.integrations.is_google_oauth_configured", return_value=False):
        with pytest.raises(HTTPException) as exc:
            get_gmail_oauth_url_endpoint(tenant)
        assert exc.value.status_code == 400
        assert "Google OAuth is not configured" in exc.value.detail


def test_gmail_oauth_url_endpoint_when_configured():
    """Endpoint returns valid OAuth authorization URL and CSRF state."""
    from backend.api.dependencies import TenantContext
    from backend.api.routes.integrations import get_gmail_oauth_url_endpoint

    tenant = TenantContext(organization_id="org-test", user_id="user-1")

    with patch("backend.api.routes.integrations.is_google_oauth_configured", return_value=True), \
         patch("backend.api.routes.integrations.get_google_auth_url", return_value=("https://accounts.google.com/test", "state-123")):
        res = get_gmail_oauth_url_endpoint(tenant)
        assert res.url == "https://accounts.google.com/test"
        assert res.state == "state-123"
        assert res.configured is True


def test_gmail_oauth_callback_endpoint_success():
    """POST /gmail/oauth/callback validates CSRF, exchanges code, and saves connection."""
    from backend.api.dependencies import TenantContext
    from backend.api.schemas import OAuthCallbackRequest
    from backend.api.routes.integrations import handle_gmail_oauth_callback

    tenant = TenantContext(organization_id="org-oauth", user_id="user-1")
    manager = IntegrationManager()

    req = OAuthCallbackRequest(code="auth_code_123", state="state_xyz")

    with patch("backend.api.routes.integrations.verify_and_consume_oauth_state", return_value={"organization_id": "org-oauth", "redirect_uri": "http://cb"}), \
         patch("backend.api.routes.integrations.exchange_google_code", return_value={"access_token": "ya29.live", "refresh_token": "1//ref"}), \
         patch("backend.api.routes.integrations.fetch_google_user_email", return_value="alice@business.com"):
        res = handle_gmail_oauth_callback(req, tenant, manager)

    assert res.status == "connected"
    assert res.integration == "gmail"
    assert res.account_identifier == "alice@business.com"

    # Connection in manager must be active
    conn = manager.get_connection("org-oauth", "gmail")
    assert conn.status == "connected"
    assert conn.account_identifier == "alice@business.com"


def test_gmail_oauth_callback_endpoint_invalid_state_rejected():
    """POST /gmail/oauth/callback must reject invalid or replayed CSRF states."""
    from fastapi import HTTPException
    from backend.api.dependencies import TenantContext
    from backend.api.schemas import OAuthCallbackRequest
    from backend.api.routes.integrations import handle_gmail_oauth_callback

    tenant = TenantContext(organization_id="org-oauth", user_id="user-1")
    manager = IntegrationManager()

    req = OAuthCallbackRequest(code="auth_code_123", state="invalid_state")

    with patch("backend.api.routes.integrations.verify_and_consume_oauth_state", return_value=None):
        with pytest.raises(HTTPException) as exc:
            handle_gmail_oauth_callback(req, tenant, manager)
        assert exc.value.status_code == 400
        assert "Invalid or expired OAuth state" in exc.value.detail


def test_gmail_oauth_browser_callback_popup_html():
    """GET /gmail/oauth/callback must render valid HTML postMessage script for browser popup."""
    from backend.api.routes.integrations import handle_gmail_oauth_browser_callback

    manager = IntegrationManager()

    with patch("backend.api.routes.integrations.verify_and_consume_oauth_state", return_value={"organization_id": "org-browser", "redirect_uri": "http://cb"}), \
         patch("backend.api.routes.integrations.exchange_google_code", return_value={"access_token": "ya29.live"}), \
         patch("backend.api.routes.integrations.fetch_google_user_email", return_value="popup@business.com"):
        html_resp = handle_gmail_oauth_browser_callback(code="code_123", state="state_browser", manager=manager)

    assert html_resp.status_code == 200
    content = html_resp.body.decode("utf-8")
    assert "Gmail Connected!" in content
    assert "OAUTH_COMPLETE" in content
    assert "popup@business.com" in content

