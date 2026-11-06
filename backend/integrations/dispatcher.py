"""
dispatcher.py
Dispatches tool execution to the appropriate integration handler
and formats the response according to the normalized n8n contract (Section 8.2):
{
  "success": bool,
  "provider_reference": str,
  "normalized_data": dict,
  "error_code": Optional[str],
  "error_message": Optional[str]
}
"""
import uuid
import logging
from typing import Any

from . import crm_integration
from . import gmail_integration
from . import slack_integration

logger = logging.getLogger(__name__)


def dispatch_tool(tool_name: str, parameters: dict) -> dict:
    """
    Execute tool against integration and return normalized payload.
    """
    ref_id = str(uuid.uuid4())

    try:
        if tool_name == "crm.find_customer":
            data = crm_integration.find_customer(parameters)
        elif tool_name == "crm.find_order":
            data = crm_integration.find_order(parameters)
        elif tool_name == "crm.create_ticket":
            data = crm_integration.create_ticket(parameters)
        elif tool_name == "crm.update_customer":
            data = crm_integration.update_customer(parameters)
        elif tool_name == "gmail.search":
            data = gmail_integration.search_emails(parameters)
        elif tool_name == "gmail.send":
            data = gmail_integration.send_email(parameters)
        elif tool_name == "slack.send_message":
            data = slack_integration.send_message(parameters)
        elif tool_name == "whatsapp.send_message":
            # Stub for whatsapp
            data = {"message_id": f"wa_{ref_id[:8]}", "status": "sent"}
        elif tool_name == "calendar.find_slot":
            data = {"slots": [{"start": "2026-11-10T10:00:00Z", "end": "2026-11-10T10:30:00Z"}]}
        elif tool_name == "calendar.create_event":
            data = {"event_id": f"evt_{ref_id[:8]}", "status": "confirmed", "meeting_link": "https://meet.google.com/abc-demo"}
        else:
            return {
                "success": False,
                "provider_reference": ref_id,
                "normalized_data": {},
                "error_code": "UNKNOWN_TOOL",
                "error_message": f"Tool '{tool_name}' has no integration handler",
            }

        return {
            "success": True,
            "provider_reference": ref_id,
            "normalized_data": data,
            "error_code": None,
            "error_message": None,
            # Also merge data keys top-level for convenience in template resolution
            **data,
        }

    except Exception as e:
        logger.error(f"Dispatch error for {tool_name}: {e}")
        return {
            "success": False,
            "provider_reference": ref_id,
            "normalized_data": {},
            "error_code": "EXECUTION_EXCEPTION",
            "error_message": str(e),
        }
