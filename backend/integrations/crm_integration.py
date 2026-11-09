"""
crm_integration.py
Handles CRM operations: find_customer, find_order, create_ticket, update_customer.
Loads data from database/demo_crm_data.json and persists in-memory changes.
"""
import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parents[2] / "database" / "demo_crm_data.json"
_crm_state: Optional[dict] = None


def _get_crm_data() -> dict:
    global _crm_state
    if _crm_state is None:
        if _DATA_PATH.exists():
            with open(_DATA_PATH, "r", encoding="utf-8") as f:
                _crm_state = json.load(f)
        else:
            _crm_state = {"customers": [], "orders": [], "tickets": []}
    return _crm_state


def find_customer(parameters: dict) -> dict:
    """
    Find customers matching query, customer_id, or email.
    """
    data = _get_crm_data()
    customers = data.get("customers", [])
    
    cid = parameters.get("customer_id")
    email = parameters.get("email")
    query = parameters.get("query", "").lower()

    results = []
    for c in customers:
        if cid and c.get("customer_id") == cid:
            results.append(c)
            continue
        if email and c.get("email", "").lower() == email.lower():
            results.append(c)
            continue
        if query:
            if query in c.get("name", "").lower() or query in c.get("email", "").lower() or query in c.get("customer_id", "").lower():
                results.append(c)

    # If no filters provided, return all (capped at 20)
    if not cid and not email and not query:
        results = customers[:20]

    return {
        "customers": results,
        "count": len(results),
    }


def find_order(parameters: dict) -> dict:
    """
    Find orders matching customer_id, status, or delayed_more_than_days.
    """
    data = _get_crm_data()
    orders = data.get("orders", [])

    cid = parameters.get("customer_id")
    order_id = parameters.get("order_id")
    status = parameters.get("status")
    delayed_days = parameters.get("delayed_more_than_days")

    results = []
    for o in orders:
        if order_id and o.get("order_id") != order_id:
            continue
        if cid and o.get("customer_id") != cid:
            continue
        if status and o.get("status") != status:
            continue
        if delayed_days is not None and o.get("delay_days", 0) < delayed_days:
            continue
        results.append(o)

    return {
        "orders": results,
        "count": len(results),
    }


def create_ticket(parameters: dict) -> dict:
    """
    Create a new support ticket.
    """
    data = _get_crm_data()
    tickets = data.get("tickets", [])

    ticket_id = f"TCK-{len(tickets) + 1:04d}"
    new_ticket = {
        "ticket_id": ticket_id,
        "customer_id": parameters.get("customer_id"),
        "order_id": parameters.get("order_id"),
        "priority": parameters.get("priority", "medium"),
        "title": parameters.get("title"),
        "description": parameters.get("description"),
        "status": "open",
    }
    tickets.append(new_ticket)
    logger.info(f"Created CRM ticket: {ticket_id} for customer {new_ticket['customer_id']}")

    return {
        "ticket_id": ticket_id,
        "status": "created",
    }


def update_customer(parameters: dict) -> dict:
    """
    Update customer details in the CRM.
    """
    data = _get_crm_data()
    customers = data.get("customers", [])

    cid = parameters.get("customer_id")
    updates = parameters.get("updates", {})

    found = False
    for c in customers:
        if c.get("customer_id") == cid:
            c.update(updates)
            found = True
            break

    return {
        "customer_id": cid,
        "updated": found,
    }
