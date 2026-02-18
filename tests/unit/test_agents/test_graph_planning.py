"""Tests for auto-planning integration in GraphOrchestrator."""

from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lidco.agents.base import AgentConfig, AgentResponse, BaseAgent
from lidco.agents.graph import GraphOrchestrator, GraphState
from lidco.agents.registry import AgentRegistry
from lidco.llm.base import LLMResponse


class _MockAgent(BaseAgent):
    """Minimal agent for testing."""

    def __init__(self, name: str = "coder", response_content: str = "done") -> None:
        config = AgentConfig(
            name=name,
            description=f"{name} agent",
            system_prompt="test",
        )
        llm = MagicMock()
        registry = MagicMock()
        super().__init__(config=config, llm=llm, tool_registry=registry)
        self._response_content = response_content

    def get_system_prompt(self) -> str:
        return "test"

    async def run(self, message: str, *, context: str = "") -> AgentResponse:
        return AgentResponse(content=self._response_content, iterations=1)


def _make_registry(*agent_names: str) -> AgentRegistry:
    """Create a registry with mock agents."""
    reg = AgentRegistry()
    for name in agent_names:
        reg.register(_MockAgent(name=name, response_content=f"{name} response"))
    return reg


def _make_llm_response(agent: str, needs_review: bool = False, needs_planning: bool = False) -> MagicMock:
    """Create a mock LLM that returns a router JSON response."""
    payload = json.dumps({
        "agent": agent,
        "needs_review": needs_review,
        "needs_planning": needs_planning,
    })
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        content=payload, model="test",
    ))
    return llm


class TestRouteDetectsNeedsPlanning:
    """Router correctly sets needs_planning based on LLM response."""

    @pytest.mark.asyncio
    async def test_route_detects_needs_planning(self):
        llm = _make_llm_response("coder", needs_planning=True)
        registry = _make_registry("coder", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=False)

        state: GraphState = {
            "user_message": "add OAuth2 authentication",
            "context": "",
            "selected_agent": "",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
        }

        result = await orch._route_node(state)
        assert result["needs_planning"] is True
        assert result["selected_agent"] == "coder"

    @pytest.mark.asyncio
    async def test_route_skips_planning_for_simple(self):
        llm = _make_llm_response("coder", needs_planning=False)
        registry = _make_registry("coder", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry)

        state: GraphState = {
            "user_message": "fix typo in readme",
            "context": "",
            "selected_agent": "",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
        }

        result = await orch._route_node(state)
        assert result["needs_planning"] is False


class TestPlanGateRouting:
    """Plan gate correctly routes to planner or skips."""

    def test_needs_planning_routes_to_plan(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)

        state: GraphState = {
            "user_message": "add feature",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": True,
            "plan_response": None,
            "plan_approved": False,
        }

        assert orch._needs_planning(state) == "plan"

    def test_no_planning_skips(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)

        state: GraphState = {
            "user_message": "fix bug",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
        }

        assert orch._needs_planning(state) == "skip"

    def test_non_coder_agent_skips_planning(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "planner", "reviewer")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)

        state: GraphState = {
            "user_message": "review code",
            "context": "",
            "selected_agent": "reviewer",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": True,
            "plan_response": None,
            "plan_approved": False,
        }

        assert orch._needs_planning(state) == "skip"

    def test_auto_plan_disabled_skips(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=False)

        state: GraphState = {
            "user_message": "add feature",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": True,
            "plan_response": None,
            "plan_approved": False,
        }

        assert orch._needs_planning(state) == "skip"


class TestPlannerExecution:
    """Planner agent runs and produces a plan."""

    @pytest.mark.asyncio
    async def test_planner_runs_before_coder(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)

        state: GraphState = {
            "user_message": "add OAuth2",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": True,
            "plan_response": None,
            "plan_approved": False,
        }

        result = await orch._execute_planner_node(state)
        assert result["plan_response"] is not None
        assert result["plan_response"].content == "planner response"

    @pytest.mark.asyncio
    async def test_planner_missing_skips_gracefully(self):
        llm = AsyncMock()
        registry = _make_registry("coder")  # no planner registered
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)

        state: GraphState = {
            "user_message": "add feature",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": True,
            "plan_response": None,
            "plan_approved": False,
        }

        result = await orch._execute_planner_node(state)
        assert result["plan_response"] is None
        assert result["plan_approved"] is True


class TestPlanApproval:
    """Plan approval node handles user responses."""

    @pytest.mark.asyncio
    async def test_plan_approval_proceeds_to_coder(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)
        orch.set_clarification_handler(lambda q, opts, ctx: "Approve")

        plan = AgentResponse(content="Step 1: do X\nStep 2: do Y", iterations=1)
        state: GraphState = {
            "user_message": "add feature",
            "context": "existing context",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": True,
            "plan_response": plan,
            "plan_approved": False,
        }

        result = await orch._approve_plan_node(state)
        assert result["plan_approved"] is True
        assert "Implementation Plan (approved)" in result["context"]
        assert "Step 1: do X" in result["context"]

    @pytest.mark.asyncio
    async def test_plan_rejection_returns_plan(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)
        orch.set_clarification_handler(lambda q, opts, ctx: "Reject")

        plan = AgentResponse(content="The plan content", iterations=1)
        state: GraphState = {
            "user_message": "add feature",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": True,
            "plan_response": plan,
            "plan_approved": False,
        }

        result = await orch._approve_plan_node(state)
        assert result["plan_approved"] is False
        assert result["agent_response"] is plan

    @pytest.mark.asyncio
    async def test_plan_edit_adds_user_edits_to_context(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)
        orch.set_clarification_handler(
            lambda q, opts, ctx: "Also add rate limiting to step 2"
        )

        plan = AgentResponse(content="Step 1: auth\nStep 2: endpoints", iterations=1)
        state: GraphState = {
            "user_message": "add feature",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": True,
            "plan_response": plan,
            "plan_approved": False,
        }

        result = await orch._approve_plan_node(state)
        assert result["plan_approved"] is True
        assert "User Edits" in result["context"]
        assert "rate limiting" in result["context"]


class TestPlanApprovedRouting:
    """_plan_approved correctly routes based on approval state."""

    def test_approved_routes_to_execute(self):
        llm = AsyncMock()
        registry = _make_registry("coder")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry)

        state: GraphState = {
            "user_message": "",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": True,
            "plan_response": None,
            "plan_approved": True,
        }

        assert orch._plan_approved(state) == "approved"

    def test_rejected_routes_to_finalize(self):
        llm = AsyncMock()
        registry = _make_registry("coder")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry)

        state: GraphState = {
            "user_message": "",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": True,
            "plan_response": None,
            "plan_approved": False,
        }

        assert orch._plan_approved(state) == "rejected"


class TestExplicitAgentSkipsPlanning:
    """When an agent is explicitly selected, planning is skipped."""

    @pytest.mark.asyncio
    async def test_explicit_agent_skips_planning(self):
        llm = _make_llm_response("coder", needs_planning=True)
        registry = _make_registry("coder", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)

        # When agent_name is explicitly provided, routing is skipped entirely
        # and the graph goes through execute_agent directly
        response = await orch.handle("add feature", agent_name="coder")
        assert response.content == "coder response"


class TestReviewLoop:
    """Review loop sends code back for fixes when issues are found."""

    def test_should_fix_returns_fix_on_critical(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "reviewer")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, max_review_iterations=2)

        review = AgentResponse(
            content="CRITICAL: SQL injection in query builder", iterations=1,
        )
        state: GraphState = {
            "user_message": "",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": True,
            "review_response": review,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 1,
        }

        assert orch._should_fix(state) == "fix"

    def test_should_fix_returns_fix_on_high(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "reviewer")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, max_review_iterations=2)

        review = AgentResponse(
            content="HIGH: Missing error handling in API endpoint", iterations=1,
        )
        state: GraphState = {
            "user_message": "",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": True,
            "review_response": review,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 1,
        }

        assert orch._should_fix(state) == "fix"

    def test_should_fix_returns_done_on_no_issues(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "reviewer")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, max_review_iterations=2)

        review = AgentResponse(
            content="NO_ISSUES_FOUND - code looks good", iterations=1,
        )
        state: GraphState = {
            "user_message": "",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": True,
            "review_response": review,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 1,
        }

        assert orch._should_fix(state) == "done"

    def test_should_fix_returns_done_on_medium_only(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "reviewer")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, max_review_iterations=2)

        review = AgentResponse(
            content="MEDIUM: Consider adding docstrings", iterations=1,
        )
        state: GraphState = {
            "user_message": "",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": True,
            "review_response": review,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 1,
        }

        assert orch._should_fix(state) == "done"

    def test_should_fix_stops_at_max_iterations(self):
        llm = AsyncMock()
        registry = _make_registry("coder", "reviewer")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, max_review_iterations=2)

        review = AgentResponse(
            content="CRITICAL: Still has issues", iterations=1,
        )
        state: GraphState = {
            "user_message": "",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": True,
            "review_response": review,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 2,  # already at max
        }

        assert orch._should_fix(state) == "done"

    def test_should_fix_returns_done_when_no_review(self):
        llm = AsyncMock()
        registry = _make_registry("coder")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, max_review_iterations=2)

        state: GraphState = {
            "user_message": "",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": True,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 1,
        }

        assert orch._should_fix(state) == "done"


class TestReviewFeedbackInjection:
    """Execute agent injects review feedback when in fix loop."""

    @pytest.mark.asyncio
    async def test_review_feedback_injected_on_fix_pass(self):
        """When review_iteration > 0, review feedback is included in message."""
        llm = AsyncMock()
        registry = AgentRegistry()

        # Track what message the coder receives
        received_messages: list[str] = []

        class TrackingAgent(_MockAgent):
            async def run(self, message: str, *, context: str = "") -> AgentResponse:
                received_messages.append(message)
                return AgentResponse(content="fixed", iterations=1)

        registry.register(TrackingAgent(name="coder"))

        orch = GraphOrchestrator(llm=llm, agent_registry=registry)

        review = AgentResponse(content="HIGH: Missing validation", iterations=1)
        state: GraphState = {
            "user_message": "add endpoint",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": True,
            "review_response": review,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 1,
        }

        result = await orch._execute_agent_node(state)
        assert result["agent_response"].content == "fixed"
        assert "REVIEW FEEDBACK" in received_messages[0]
        assert "Missing validation" in received_messages[0]

    @pytest.mark.asyncio
    async def test_no_review_feedback_on_first_pass(self):
        """On first pass (review_iteration=0), no review feedback."""
        llm = AsyncMock()
        registry = AgentRegistry()

        received_messages: list[str] = []

        class TrackingAgent(_MockAgent):
            async def run(self, message: str, *, context: str = "") -> AgentResponse:
                received_messages.append(message)
                return AgentResponse(content="done", iterations=1)

        registry.register(TrackingAgent(name="coder"))

        orch = GraphOrchestrator(llm=llm, agent_registry=registry)

        state: GraphState = {
            "user_message": "add endpoint",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 0,
        }

        await orch._execute_agent_node(state)
        assert "REVIEW FEEDBACK" not in received_messages[0]


class TestPlannerContextPassthrough:
    """Planner tool results are passed to coder context."""

    @pytest.mark.asyncio
    async def test_planner_tool_calls_in_coder_context(self):
        llm = AsyncMock()
        registry = AgentRegistry()

        received_contexts: list[str] = []

        class TrackingAgent(_MockAgent):
            async def run(self, message: str, *, context: str = "") -> AgentResponse:
                received_contexts.append(context)
                return AgentResponse(content="coded", iterations=1)

        registry.register(TrackingAgent(name="coder"))

        orch = GraphOrchestrator(llm=llm, agent_registry=registry)

        plan = AgentResponse(
            content="Plan: modify auth.py",
            iterations=1,
            tool_calls_made=[
                {"tool": "file_read", "args": {"path": "src/auth.py"}, "result": "class Auth:..."},
                {"tool": "grep", "args": {"pattern": "login", "path": "src/"}, "result": "3 matches"},
            ],
        )

        state: GraphState = {
            "user_message": "add auth",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": True,
            "plan_response": plan,
            "plan_approved": True,
            "review_iteration": 0,
        }

        await orch._execute_agent_node(state)
        assert "Planner Exploration Results" in received_contexts[0]
        assert "file_read" in received_contexts[0]
        assert "src/auth.py" in received_contexts[0]

    @pytest.mark.asyncio
    async def test_no_planner_context_when_no_plan(self):
        llm = AsyncMock()
        registry = AgentRegistry()

        received_contexts: list[str] = []

        class TrackingAgent(_MockAgent):
            async def run(self, message: str, *, context: str = "") -> AgentResponse:
                received_contexts.append(context)
                return AgentResponse(content="done", iterations=1)

        registry.register(TrackingAgent(name="coder"))

        orch = GraphOrchestrator(llm=llm, agent_registry=registry)

        state: GraphState = {
            "user_message": "fix bug",
            "context": "",
            "selected_agent": "coder",
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 0,
        }

        await orch._execute_agent_node(state)
        assert "Planner Exploration" not in received_contexts[0]
