"""
tests/test_agent.py
Unit tests for all Phase 2 agent modules.
Run with: python -m pytest tests/ -v
"""
import json
import pytest
from unittest.mock import patch, MagicMock

# ─────────────────────────────────────────
# Tool Registry Tests
# ─────────────────────────────────────────
class TestToolRegistry:
    def test_tool_exists(self):
        from backend.agent.tool_registry import tool_exists
        assert tool_exists("crm.find_order") is True
        assert tool_exists("nonexistent.tool") is False

    def test_get_tool(self):
        from backend.agent.tool_registry import get_tool
        t = get_tool("gmail.send")
        assert t is not None
        assert t["risk_level"] == "medium"
        assert t["required_permission"] == "gmail.send"

    def test_list_tools(self):
        from backend.agent.tool_registry import list_tools
        tools = list_tools()
        assert len(tools) == 10
        names = [t["name"] for t in tools]
        assert "crm.create_ticket" in names
        assert "slack.send_message" in names

    def test_tools_summary_for_prompt(self):
        from backend.agent.tool_registry import get_tools_summary_for_prompt
        summary = get_tools_summary_for_prompt()
        assert "gmail.send" in summary
        assert "crm.find_order" in summary


# ─────────────────────────────────────────
# Tool Selector Tests
# ─────────────────────────────────────────
class TestToolSelector:
    def test_valid_tool_enriched(self):
        from backend.agent.tool_selector import select_and_enrich
        plan = {
            "mode": "ASK",
            "goal": "test",
            "steps": [{"id": "step_1", "tool": "crm.find_order", "parameters": {"status": "delayed"}}]
        }
        result = select_and_enrich(plan)
        assert result["steps"][0]["_tool_def"]["name"] == "crm.find_order"

    def test_invalid_tool_raises(self):
        from backend.agent.tool_selector import select_and_enrich, ToolSelectionError
        plan = {
            "mode": "DO",
            "goal": "test",
            "steps": [{"id": "step_1", "tool": "not.a.real.tool", "parameters": {}}]
        }
        with pytest.raises(ToolSelectionError):
            select_and_enrich(plan)


# ─────────────────────────────────────────
# Validator Tests
# ─────────────────────────────────────────
class TestValidator:
    def test_valid_params_pass(self):
        from backend.agent.validator import validate_plan
        plan = {
            "steps": [{
                "id": "step_1",
                "tool": "crm.create_ticket",
                "parameters": {
                    "customer_id": "CUST-001",
                    "priority": "high",
                    "title": "Order Delayed",
                    "description": "Order delayed by 3 days"
                }
            }]
        }
        result = validate_plan(plan)
        assert result is not None

    def test_missing_required_param_fails(self):
        from backend.agent.validator import validate_plan, ValidationError
        plan = {
            "steps": [{
                "id": "step_1",
                "tool": "crm.create_ticket",
                "parameters": {
                    "customer_id": "CUST-001"
                    # missing priority, title, description
                }
            }]
        }
        with pytest.raises(ValidationError):
            validate_plan(plan)

    def test_template_references_skipped(self):
        from backend.agent.validator import validate_plan
        plan = {
            "steps": [{
                "id": "step_2",
                "tool": "gmail.send",
                "parameters": {
                    "to": "{{step_1.customer_email}}",  # template reference
                    "subject": "Order Update",
                    "body": "Your order status has been updated."
                }
            }]
        }
        # Should not raise — template ref is skipped
        result = validate_plan(plan)
        assert result is not None


# ─────────────────────────────────────────
# Permission Manager Tests
# ─────────────────────────────────────────
class TestPermissionManager:
    def test_has_permission_passes(self):
        from backend.agent.permission_manager import check_permissions
        plan = {"steps": [{"id": "step_1", "tool": "crm.find_order", "parameters": {}}]}
        result = check_permissions(plan, ["crm.read", "gmail.send"], "user-1")
        assert result is not None

    def test_missing_permission_raises(self):
        from backend.agent.permission_manager import check_permissions, PermissionDeniedError
        plan = {"steps": [{"id": "step_1", "tool": "gmail.send", "parameters": {}}]}
        with pytest.raises(PermissionDeniedError):
            check_permissions(plan, ["crm.read"], "user-1")  # no gmail.send


# ─────────────────────────────────────────
# Confirmation Manager Tests
# ─────────────────────────────────────────
class TestConfirmationManager:
    def test_low_risk_no_confirmation(self):
        from backend.agent.confirmation_manager import evaluate_confirmation
        plan = {"steps": [{"id": "step_1", "tool": "crm.find_order", "parameters": {}}]}
        result = evaluate_confirmation(plan)
        assert result["steps"][0]["requires_confirmation"] is False
        assert result["requires_confirmation"] is False

    def test_medium_risk_needs_confirmation(self):
        from backend.agent.confirmation_manager import evaluate_confirmation
        plan = {"steps": [{"id": "step_1", "tool": "gmail.send", "parameters": {}}]}
        result = evaluate_confirmation(plan)
        assert result["steps"][0]["requires_confirmation"] is True
        assert result["requires_confirmation"] is True


# ─────────────────────────────────────────
# Context Manager Tests
# ─────────────────────────────────────────
class TestContextManager:
    def test_template_resolution(self):
        from backend.agent.context_manager import ConversationContext
        ctx = ConversationContext(user_id="u1", org_id="org1")
        ctx.store_step_output("step_1", {"count": 5, "orders": [{"customer_id": "CUST-001"}]})
        
        params = {"message": "Found {{step_1.count}} orders"}
        resolved = ctx.resolve_templates(params)
        assert resolved["message"] == "Found 5 orders"

    def test_nested_template_resolution(self):
        from backend.agent.context_manager import ConversationContext
        ctx = ConversationContext(user_id="u1", org_id="org1")
        ctx.store_step_output("step_1", {"customer_id": "CUST-001"})
        
        params = {"customer_id": "{{step_1.customer_id}}"}
        resolved = ctx.resolve_templates(params)
        assert resolved["customer_id"] == "CUST-001"


# ─────────────────────────────────────────
# Planner Tests (mocked Gemini)
# ─────────────────────────────────────────
class TestPlanner:
    @patch("backend.agent.planner.genai")
    def test_plan_ask_mode(self, mock_genai):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "mode": "ASK",
            "goal": "Count delayed orders",
            "requires_confirmation": False,
            "steps": [{"id": "step_1", "tool": "crm.find_order", "parameters": {"status": "delayed"}, "depends_on": [], "description": "Find delayed orders"}],
            "clarification_needed": False,
            "clarification_question": None
        })
        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_response
        mock_genai.GenerativeModel.return_value.start_chat.return_value = mock_chat

        import os
        os.environ["GEMINI_API_KEY"] = "test-key"
        
        from backend.agent.planner import plan
        result = plan("How many delayed orders?")
        assert result["mode"] == "ASK"
        assert result["steps"][0]["tool"] == "crm.find_order"


# ─────────────────────────────────────────
# Full Agent Integration Test (dry run)
# ─────────────────────────────────────────
class TestAgentIntegration:
    @patch("backend.agent.planner.genai")
    def test_full_ask_flow_dry_run(self, mock_genai):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "mode": "ASK",
            "goal": "Count delayed orders",
            "requires_confirmation": False,
            "steps": [{"id": "step_1", "tool": "crm.find_order", "parameters": {"status": "delayed"}, "depends_on": [], "description": "Find delayed orders"}],
            "clarification_needed": False,
            "clarification_question": None
        })
        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_response
        mock_genai.GenerativeModel.return_value.start_chat.return_value = mock_chat

        import os
        os.environ["GEMINI_API_KEY"] = "test-key"

        from backend.agent.agent import Agent
        from backend.agent.context_manager import ConversationContext

        ctx = ConversationContext(user_id="u1", org_id="org1")
        agent = Agent()
        
        with patch("backend.agent.response_generator.genai") as mock_resp_genai:
            mock_resp = MagicMock()
            mock_resp.text = "I found 10 delayed orders in the system."
            mock_resp_genai.GenerativeModel.return_value.generate_content.return_value = mock_resp
            
            result = agent.run(
                "How many delayed orders do we have?",
                ctx,
                user_permissions=["crm.read"],
                dry_run=True,
            )
        
        assert result.status == "completed"
        assert result.mode == "ASK"
        assert result.run_id is not None
