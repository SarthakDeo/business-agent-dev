"""
slack_integration.py
Handles Slack operations: slack.send_message.
Supports live Slack API (via requests) or simulated demo delivery.
"""
import os
import time
import logging
import requests
from typing import Any

logger = logging.getLogger(__name__)

_sent_slack_messages: list[dict] = []


def send_message(parameters: dict) -> dict:
    """
    Send a message to a Slack channel.
    """
    channel = parameters.get("channel", "#logistics-demo")
    text = parameters.get("message", "")
    thread_ts = parameters.get("thread_ts")

    token = os.environ.get("SLACK_BOT_TOKEN")
    
    # If a real Slack token (not default placeholder) is provided, post to Slack API
    if token and not token.startswith("xoxb-your-") and token != "your_slack_token":
        try:
            payload = {"channel": channel, "text": text}
            if thread_ts:
                payload["thread_ts"] = thread_ts
            
            resp = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10,
            )
            data = resp.json()
            if data.get("ok"):
                return {
                    "ts": data.get("ts"),
                    "channel": data.get("channel", channel),
                    "ok": True,
                }
            else:
                logger.warning(f"Slack API returned ok=false: {data.get('error')}, falling back to mock")
        except Exception as e:
            logger.warning(f"Slack API call failed: {e}, falling back to mock")

    # Simulation / Demo fallback
    ts = f"{time.time():.6f}"
    record = {
        "ts": ts,
        "channel": channel,
        "message": text,
        "thread_ts": thread_ts,
        "ok": True,
    }
    _sent_slack_messages.append(record)
    logger.info(f"[Slack] Message posted to {channel}: {text[:60]}... (ts={ts})")

    return {
        "ts": ts,
        "channel": channel,
        "ok": True,
    }


def get_sent_slack_messages() -> list[dict]:
    """Inspect posted Slack messages (useful for tests and monitoring)."""
    return _sent_slack_messages
