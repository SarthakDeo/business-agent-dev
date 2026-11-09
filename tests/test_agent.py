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
        mock_genai.Client.return_value.chats.create.return_value = mock_chat

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
        mock_genai.Client.return_value.chats.create.return_value = mock_chat

        import os
        os.environ["GEMINI_API_KEY"] = "test-key"

        from backend.agent.agent import Agent
        from backend.agent.context_manager import ConversationContext

        ctx = ConversationContext(user_id="u1", org_id="org1")
        agent = Agent()
        
        with patch("backend.agent.response_generator.genai") as mock_resp_genai:
            mock_resp = MagicMock()
            mock_resp.text = "I found 10 delayed orders in the system."
            mock_resp_genai.Client.return_value.models.generate_content.return_value = mock_resp
            
            result = agent.run(
                "How many delayed orders do we have?",
                ctx,
                user_permissions=["crm.read"],
                dry_run=True,
            )
        
        assert result.status == "completed"
        assert result.mode == "ASK"
        assert result.run_id is not None


class TestPhase2Hardening:
    def _slack_plan(self):
        return {
            "mode": "DO",
            "goal": "Notify support",
            "steps": [{
                "id": "step_1",
                "tool": "slack.send_message",
                "parameters": {
                    "channel": "#support",
                    "message": "New customer complaint",
                },
            }],
        }

    def test_full_write_flow_requires_and_accepts_confirmation(self):
        from backend.agent.agent import Agent
        from backend.agent.context_manager import ConversationContext
        from backend.agent.response_generator import ResponseGenerationResult

        agent = Agent()
        context = ConversationContext("u1", "org1")
        context.integration_manager.connect("org1", "slack", "test-slack-secret")
        planned = self._slack_plan()
        first_response = ResponseGenerationResult("Approval needed", "success")
        final_response = ResponseGenerationResult("Message sent", "success")

        with patch("backend.agent.agent.plan", return_value=planned), \
             patch("backend.agent.agent.generate_response_result", return_value=first_response), \
             patch("backend.agent.execution_manager._call_n8n", side_effect=__import__("requests").RequestException()), \
             patch("backend.agent.execution_manager.dispatch_tool", return_value={
                 "success": True, "ok": True, "channel": "#support",
             }) as dispatch, \
             patch("backend.agent.agent.generate_response_result", side_effect=[
                 first_response, final_response,
             ]):
            pending = agent.run("Send a support Slack message", context, ["slack.send"])
            assert pending.status == "awaiting_confirmation"
            assert pending.pending_confirmations
            dispatch.assert_not_called()

            completed = agent.resume_confirmation(context, approved=True)

        assert completed.status == "completed"
        assert completed.response_text == "Message sent"
        dispatch.assert_called_once()

    def test_direct_unapproved_medium_tool_is_blocked(self):
        from backend.agent.context_manager import ConversationContext
        from backend.agent.execution_manager import execute_plan

        context = ConversationContext("u1", "org1")
        context.integration_manager.connect("org1", "slack", "test-slack-secret")
        with patch("backend.agent.execution_manager._call_n8n") as call:
            results = execute_plan({
                "steps": [{
                    "id": "step_1",
                    "tool": "slack.send_message",
                    "parameters": {"channel": "#support", "message": "x"},
                }],
            }, context)

        assert results["step_1"]["error_code"] == "CONFIRMATION_REQUIRED"
        call.assert_not_called()

    def test_direct_approved_medium_tool_executes(self):
        from backend.agent.context_manager import ConversationContext
        from backend.agent.execution_manager import execute_plan
        import requests

        context = ConversationContext("u1", "org1")
        context.approved_step_ids.add("step_1")
        context.integration_manager.connect("org1", "slack", "test-slack-secret")
        with patch("backend.agent.execution_manager._call_n8n", side_effect=requests.RequestException()), \
             patch("backend.agent.execution_manager.dispatch_tool", return_value={
                 "success": True, "ok": True,
             }) as dispatch:
            results = execute_plan({
                "steps": [{
                    "id": "step_1",
                    "tool": "slack.send_message",
                    "parameters": {"channel": "#support", "message": "x"},
                }],
            }, context)

        assert results["step_1"]["success"] is True
        dispatch.assert_called_once()

    def test_low_risk_tool_executes_without_approval(self):
        from backend.agent.context_manager import ConversationContext
        from backend.agent.execution_manager import execute_plan
        import requests

        context = ConversationContext("u1", "org1")
        context.integration_manager.connect("org1", "crm", "test-crm-secret")
        with patch("backend.agent.execution_manager._call_n8n", side_effect=requests.RequestException()), \
             patch("backend.agent.execution_manager.dispatch_tool", return_value={
                 "success": True, "count": 1,
             }) as dispatch:
            results = execute_plan({
                "steps": [{
                    "id": "step_1",
                    "tool": "crm.find_order",
                    "parameters": {"status": "delayed"},
                }],
            }, context)

        assert results["step_1"]["success"] is True
        dispatch.assert_called_once()

    @pytest.mark.parametrize("plan", [
        {"mode": "INVALID", "goal": "x", "steps": []},
        {"mode": "ASK", "goal": "x"},
        {"mode": "ASK", "goal": "x", "steps": [{}]},
        {"mode": "ASK", "goal": "x", "steps": [{
            "id": "step_1", "tool": "some.fake.tool", "parameters": {},
        }]},
    ])
    def test_malformed_plans_are_rejected_before_execution(self, plan):
        from backend.agent.validator import validate_agent_plan, ValidationError

        with pytest.raises(ValidationError):
            validate_agent_plan(plan)

    def test_response_generation_failure_is_explicit(self):
        from backend.agent import response_generator

        with patch.object(response_generator, "genai", MagicMock()), \
             patch.object(response_generator.genai.Client.return_value.models,
                           "generate_content", side_effect=RuntimeError("provider failure")):
            result = response_generator.generate_response_result(
                "request", {"mode": "ASK", "goal": "test"}, {}, []
            )

        assert result.status == "fallback"
        assert result.error == "Gemini response generation failed"
        assert result.response_text

    def test_planner_failure_does_not_return_a_plan(self):
        from backend.agent import planner

        failing_genai = MagicMock()
        failing_genai.Client.return_value.chats.create.side_effect = RuntimeError("provider failure")
        with patch.object(planner, "genai", failing_genai), \
             patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            with pytest.raises(RuntimeError, match="All Gemini models failed"):
                planner.plan("request")

    def test_execution_failure_becomes_agent_error(self):
        from backend.agent.agent import Agent
        from backend.agent.context_manager import ConversationContext
        from backend.agent.response_generator import ResponseGenerationResult
        import requests

        with patch("backend.agent.agent.plan", return_value=self._slack_plan()), \
             patch("backend.agent.agent.generate_response_result",
                   return_value=ResponseGenerationResult("Approval needed", "success")), \
             patch("backend.agent.execution_manager._call_n8n",
                   side_effect=requests.RequestException()), \
             patch("backend.agent.execution_manager.dispatch_tool",
                   return_value={"success": False, "error_message": "provider failed"}):
            agent = Agent()
            context = ConversationContext("u1", "org1")
            agent.run("Send message", context, ["slack.send"])
            result = agent.resume_confirmation(context, approved=True)

        assert result.status == "error"
        assert "failed" in result.response_text.lower()
