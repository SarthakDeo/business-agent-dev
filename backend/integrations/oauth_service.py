"""Google OAuth2 service for Gmail integration with CSRF state protection."""

from datetime import datetime, timezone
import logging
import os
import secrets
from typing import Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
]

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"

# In-memory CSRF state registry: state_token -> { organization_id, user_id, redirect_uri, created_at }
_oauth_states: dict[str, dict] = {}
_STATE_TTL_SECONDS = 600  # 10 minutes


def _clean_expired_states() -> None:
    now = datetime.now(timezone.utc).timestamp()
    expired = [
        state
        for state, info in _oauth_states.items()
        if now - info.get("created_at", 0) > _STATE_TTL_SECONDS
    ]
    for state in expired:
        _oauth_states.pop(state, None)


def get_google_client_id() -> Optional[str]:
    return (
        os.environ.get("GOOGLE_CLIENT_ID")
        or os.environ.get("VOICE2FLOW_GOOGLE_CLIENT_ID")
        or os.environ.get("GNANI_GOOGLE_CLIENT_ID")
    )


def get_google_client_secret() -> Optional[str]:
    return (
        os.environ.get("GOOGLE_CLIENT_SECRET")
        or os.environ.get("VOICE2FLOW_GOOGLE_CLIENT_SECRET")
        or os.environ.get("GNANI_GOOGLE_CLIENT_SECRET")
    )


def get_default_redirect_uri() -> str:
    return (
        os.environ.get("GOOGLE_REDIRECT_URI")
        or os.environ.get("VOICE2FLOW_GOOGLE_REDIRECT_URI")
        or "http://localhost:8000/api/integrations/gmail/oauth/callback"
    )


def is_google_oauth_configured() -> bool:
    client_id = get_google_client_id()
    client_secret = get_google_client_secret()
    return bool(client_id and client_secret)


def create_oauth_state(
    organization_id: str,
    user_id: str = "default",
    redirect_uri: Optional[str] = None,
) -> str:
    """Generate and store a single-use cryptographically secure OAuth CSRF state."""
    _clean_expired_states()
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "organization_id": organization_id,
        "user_id": user_id,
        "redirect_uri": redirect_uri or get_default_redirect_uri(),
        "created_at": datetime.now(timezone.utc).timestamp(),
    }
    return state


def verify_and_consume_oauth_state(
    state: str,
    organization_id: Optional[str] = None,
) -> Optional[dict]:
    """Verify and consume the OAuth state (single-use). Returns state info or None."""
    _clean_expired_states()
    info = _oauth_states.get(state)
    if not info:
        return None
    if organization_id and info.get("organization_id") != organization_id:
        return None
    now = datetime.now(timezone.utc).timestamp()
    if now - info.get("created_at", 0) > _STATE_TTL_SECONDS:
        _oauth_states.pop(state, None)
        return None
    # Valid match: consume (single-use) and return
    return _oauth_states.pop(state, None)


def get_google_auth_url(
    organization_id: str,
    user_id: str = "default",
    redirect_uri: Optional[str] = None,
) -> tuple[str, str]:
    """Build the Google OAuth 2.0 authorization URL and CSRF state."""
    client_id = get_google_client_id()
    if not client_id:
        raise ValueError("Google OAuth client ID is not configured")

    effective_redirect_uri = redirect_uri or get_default_redirect_uri()
    state = create_oauth_state(organization_id, user_id, effective_redirect_uri)

    params = {
        "client_id": client_id,
        "redirect_uri": effective_redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"
    return auth_url, state


def exchange_google_code(
    code: str,
    redirect_uri: Optional[str] = None,
) -> dict:
    """Exchange authorization code for tokens with Google's OAuth token endpoint."""
    client_id = get_google_client_id()
    client_secret = get_google_client_secret()
    if not client_id or not client_secret:
        raise ValueError("Google OAuth credentials are not configured")

    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri or get_default_redirect_uri(),
        "grant_type": "authorization_code",
    }
    resp = requests.post(GOOGLE_TOKEN_ENDPOINT, data=payload, timeout=10)
    if resp.status_code != 200:
        logger.error(f"Failed to exchange Google OAuth code: {resp.status_code} - {resp.text}")
        raise ValueError(f"Google token exchange failed: {resp.text}")
    return resp.json()


def fetch_google_user_email(access_token: str) -> Optional[str]:
    """Fetch user profile email from Google UserInfo endpoint."""
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(GOOGLE_USERINFO_ENDPOINT, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("email")
    except Exception as exc:
        logger.warning(f"Could not fetch Google user email: {exc}")
    return None
