"""
slack_integration.py
Handles demo Slack operations: slack.send_message.
"""
import time
import logging

logger = logging.getLogger(__name__)

_sent_slack_messages: list[dict] = []


def send_message(parameters: dict) -> dict:
    """Record a demo Slack message after credential resolution by the manager."""
    channel = parameters.get("channel", "#logistics-demo")
    text = parameters.get("message", "")
    thread_ts = parameters.get("thread_ts")

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

    return {"ts": ts, "channel": channel, "ok": True}


def get_sent_slack_messages() -> list[dict]:
    """Inspect posted Slack messages (useful for tests and monitoring)."""
    return _sent_slack_messages
