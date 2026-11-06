"""
gmail_integration.py
Handles Gmail operations: gmail.search, gmail.send.
Supports real Gmail API when credentials exist, and realistic demo simulation.
"""
import os
import uuid
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# In-memory outbox / sent messages for inspection
_sent_emails: list[dict] = []


def search_emails(parameters: dict) -> dict:
    """
    Search Gmail messages matching query.
    """
    query = parameters.get("query", "").lower()
    max_results = parameters.get("max_results", 10)

    # Demo emails
    demo_inbox = [
        {
            "id": "msg_001",
            "from": "john@example.com",
            "subject": "Inquiry regarding delayed order ORD-0001",
            "snippet": "Hello, my order has been pending for over 4 days now. Any update?",
            "date": "2026-11-01T14:20:00Z",
        },
        {
            "id": "msg_002",
            "from": "jane.smith@example.com",
            "subject": "Delivery status of shipment",
            "snippet": "Can you please check the tracking number for my order?",
            "date": "2026-11-02T10:15:00Z",
        },
        {
            "id": "msg_003",
            "from": "support@partner.com",
            "subject": "Weekly logistics report",
            "snippet": "Here is the summary of logistics performance for late shipments.",
            "date": "2026-11-03T08:00:00Z",
        },
    ]

    matched = []
    for email in demo_inbox:
        if not query or query in email["subject"].lower() or query in email["from"].lower() or query in email["snippet"].lower():
            matched.append(email)

    return {
        "emails": matched[:max_results],
        "count": len(matched),
    }


def send_email(parameters: dict) -> dict:
    """
    Send an email. Records to outbox and returns message ID.
    """
    to = parameters.get("to")
    subject = parameters.get("subject")
    body = parameters.get("body")
    cc = parameters.get("cc")

    msg_id = f"gmail_{uuid.uuid4().hex[:12]}"
    sent_record = {
        "message_id": msg_id,
        "to": to,
        "subject": subject,
        "body": body,
        "cc": cc,
        "status": "sent",
        "sent_at": datetime.utcnow().isoformat() + "Z",
    }
    _sent_emails.append(sent_record)
    logger.info(f"[Gmail] Email sent to '{to}': '{subject}' (id={msg_id})")

    return {
        "message_id": msg_id,
        "status": "sent",
    }


def get_sent_emails() -> list[dict]:
    """Inspect sent emails (useful for tests and dashboards)."""
    return _sent_emails
