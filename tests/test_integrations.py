"""
tests/test_integrations.py
Tests for Phase 3: CRM, Gmail, and Slack integrations + Dispatcher + Live execution.
"""
import pytest
from backend.integrations import dispatch_tool
from backend.integrations import crm_integration
from backend.integrations import gmail_integration
from backend.integrations import slack_integration
from backend.agent.context_manager import ConversationContext
from backend.agent.execution_manager import execute_plan
from backend.integrations import IntegrationManager


class TestCrmIntegration:
    def test_find_delayed_orders(self):
        result = crm_integration.find_order({"status": "delayed"})
        assert result["count"] == 10
        for o in result["orders"]:
            assert o["status"] == "delayed"
            assert o["delay_days"] > 0

    def test_find_customer_john_doe(self):
        result = crm_integration.find_customer({"customer_id": "CUST-001"})
        assert result["count"] == 1
        assert result["customers"][0]["name"] == "John Doe"
        assert result["customers"][0]["email"] == "john@example.com"

    def test_create_ticket(self):
        result = crm_integration.create_ticket({
            "customer_id": "CUST-001",
            "order_id": "ORD-0001",
            "priority": "high",
            "title": "Delivery Delay Investigation",
            "description": "Order delayed by 4 days",
        })
        assert result["status"] == "created"
        assert result["ticket_id"].startswith("TCK-")

    def test_update_customer(self):
        result = crm_integration.update_customer({
            "customer_id": "CUST-001",
            "updates": {"notes": "VIP Client"}
        })
        assert result["updated"] is True


class TestGmailIntegration:
    def test_search_emails(self):
        result = gmail_integration.search_emails({"query": "delayed"})
        assert result["count"] >= 1
        assert "emails" in result

    def test_send_email(self):
        result = gmail_integration.send_email({
            "to": "john@example.com",
            "subject": "Delay Update",
            "body": "Your order is on the way.",
        })
        assert result["status"] == "sent"
        assert result["message_id"].startswith("gmail_")


class TestSlackIntegration:
    def test_send_message(self):
        result = slack_integration.send_message({
            "channel": "#logistics-demo",
            "message": "Alert: 10 delayed orders found."
        })
        assert result["ok"] is True
        assert result["channel"] == "#logistics-demo"
        assert "ts" in result


class TestDispatcher:
    def test_dispatch_crm_normalized_contract(self):
        res = dispatch_tool("crm.find_order", {"status": "delayed"})
        assert res["success"] is True
        assert "provider_reference" in res
        assert "normalized_data" in res
        assert res["count"] == 10

    def test_dispatch_slack_normalized_contract(self):
        res = dispatch_tool("slack.send_message", {
            "channel": "#logistics-demo",
            "message": "Test notification"
        })
        assert res["success"] is True
        assert res["ok"] is True
        assert res["error_code"] is None

    def test_dispatch_unknown_tool(self):
        res = dispatch_tool("unknown.action", {})
        assert res["success"] is False
        assert res["error_code"] == "UNKNOWN_TOOL"


class TestLiveExecutionManager:
    def test_multi_step_template_execution(self):
        ctx = ConversationContext(user_id="demo-user", org_id="demo-org")
        manager = ctx.integration_manager
        manager.connect("demo-org", "crm", "test-crm-secret")
        manager.connect("demo-org", "slack", "test-slack-secret")
        
        plan = {
            "mode": "DO",
            "goal": "Find delayed orders and alert Slack",
            "steps": [
                {
                    "id": "step_1",
                    "tool": "crm.find_order",
                    "parameters": {"status": "delayed"}
                },
                {
                    "id": "step_2",
                    "tool": "slack.send_message",
                    "parameters": {
                        "channel": "#logistics-demo",
                        "message": "Discovered {{step_1.count}} delayed orders in CRM."
                    },
                    "depends_on": ["step_1"]
                }
            ]
        }
        ctx.approved_step_ids.add("step_2")

        # dry_run=False -> runs live integration dispatch
        results = execute_plan(plan, ctx, agent_run_id="run-test-1", dry_run=False)
        
        assert "step_1" in results
        assert results["step_1"]["count"] == 10
        assert "step_2" in results
        assert results["step_2"]["ok"] is True

        # Verify message text had template resolved
        sent = slack_integration.get_sent_slack_messages()
        last_msg = sent[-1]["message"]
        assert "Discovered 10 delayed orders" in last_msg
