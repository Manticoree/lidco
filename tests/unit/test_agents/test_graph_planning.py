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

    def test_non_implementation_agent_skips_planning(self):
        """reviewer and researcher are not in _PLANNING_AGENTS — skip planning."""
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
        # plan_approved is NOT set by this node; _approve_plan_node handles it
        # when plan_response is None (auto-approves with empty parallel_steps)
        assert result.get("plan_approved", False) is False


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

        assert orch._plan_approved(state) == "sequential"

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


class _MockAgentWithToolCalls(_MockAgent):
    """Mock agent with configurable multi-response behavior and tool calls."""

    def __init__(
        self,
        name: str,
        responses: list[str],
        tool_calls_per_response: list[list] | None = None,
    ) -> None:
        first = responses[0] if responses else "done"
        super().__init__(name=name, response_content=first)
        self._responses = list(responses)
        self._tool_calls_per_response = tool_calls_per_response or [[] for _ in responses]
        self.call_count = 0

    async def run(self, message: str, *, context: str = "") -> AgentResponse:
        idx = min(self.call_count, len(self._responses) - 1)
        tc = (
            self._tool_calls_per_response[idx]
            if idx < len(self._tool_calls_per_response)
            else []
        )
        self.call_count += 1
        return AgentResponse(content=self._responses[idx], tool_calls_made=tc, iterations=1)


_FAKE_TOOL_CALL = {"tool": "file_edit", "args": {"path": "src/x.py"}, "result": "ok"}


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


class TestShouldReview:
    """_should_review decides whether to enter the review loop."""

    def _make_orch(self) -> GraphOrchestrator:
        return GraphOrchestrator(
            llm=AsyncMock(),
            agent_registry=_make_registry("coder", "reviewer"),
        )

    def _state(self, **overrides) -> GraphState:
        base: GraphState = {
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
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 0,
        }
        base.update(overrides)
        return base

    def test_returns_review_when_tool_calls_present(self):
        orch = self._make_orch()
        response = AgentResponse(content="done", tool_calls_made=[_FAKE_TOOL_CALL])
        state = self._state(needs_review=True, agent_response=response)
        assert orch._should_review(state) == "review"

    def test_returns_skip_when_no_tool_calls(self):
        orch = self._make_orch()
        response = AgentResponse(content="done", tool_calls_made=[])
        state = self._state(needs_review=True, agent_response=response)
        assert orch._should_review(state) == "skip"

    def test_returns_skip_when_needs_review_false(self):
        orch = self._make_orch()
        response = AgentResponse(content="done", tool_calls_made=[_FAKE_TOOL_CALL])
        state = self._state(needs_review=False, agent_response=response)
        assert orch._should_review(state) == "skip"

    def test_returns_skip_when_no_agent_response(self):
        orch = self._make_orch()
        state = self._state(needs_review=True, agent_response=None)
        assert orch._should_review(state) == "skip"


class TestAutoReviewNode:
    """_auto_review_node executes the reviewer agent."""

    def _state_with_response(self, **overrides) -> GraphState:
        response = AgentResponse(
            content="Edited src/auth.py",
            tool_calls_made=[_FAKE_TOOL_CALL],
            iterations=1,
        )
        base: GraphState = {
            "user_message": "add auth",
            "context": "",
            "selected_agent": "coder",
            "agent_response": response,
            "conversation_history": [],
            "needs_review": True,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": False,
            "review_iteration": 0,
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_reviewer_runs_and_sets_review_response(self):
        registry = AgentRegistry()
        registry.register(_MockAgent(name="reviewer", response_content="NO_ISSUES_FOUND"))
        orch = GraphOrchestrator(llm=AsyncMock(), agent_registry=registry)

        result = await orch._auto_review_node(self._state_with_response())

        assert result["review_iteration"] == 1
        assert result["review_response"] is not None
        assert result["review_response"].content == "NO_ISSUES_FOUND"

    @pytest.mark.asyncio
    async def test_reviewer_missing_increments_iteration_only(self):
        registry = _make_registry("coder")  # no reviewer registered
        orch = GraphOrchestrator(llm=AsyncMock(), agent_registry=registry)

        result = await orch._auto_review_node(self._state_with_response())

        assert result["review_iteration"] == 1
        assert result.get("review_response") is None

    @pytest.mark.asyncio
    async def test_reviewer_exception_advances_iteration_to_prevent_infinite_loop(self):
        """On crash the iteration counter must still advance.

        If prev_iter were kept, a previously-set CRITICAL review_response would
        keep _should_fix returning "fix" forever on repeated reviewer crashes,
        causing an unbounded review→fix→review loop.
        """
        registry = AgentRegistry()

        class FailingReviewer(_MockAgent):
            async def run(self, message: str, *, context: str = "") -> AgentResponse:
                raise RuntimeError("reviewer crashed")

        registry.register(FailingReviewer(name="reviewer"))
        orch = GraphOrchestrator(llm=AsyncMock(), agent_registry=registry)

        result = await orch._auto_review_node(self._state_with_response())

        # Counter advances (from 0→1) even on crash to prevent infinite loops
        assert result["review_iteration"] == 1
        assert result.get("review_response") is None

    @pytest.mark.asyncio
    async def test_no_agent_response_increments_iteration_only(self):
        registry = AgentRegistry()
        registry.register(_MockAgent(name="reviewer", response_content="CRITICAL: issue"))
        orch = GraphOrchestrator(llm=AsyncMock(), agent_registry=registry)

        result = await orch._auto_review_node(self._state_with_response(agent_response=None))

        assert result["review_iteration"] == 1
        assert result.get("review_response") is None

    @pytest.mark.asyncio
    async def test_reviewer_receives_continue_and_error_callbacks(self):
        """Reviewer must get continue_handler and error_callback — same as execute_agent_node."""
        received: dict = {}

        class TrackingReviewer(_MockAgent):
            def set_continue_handler(self, h):
                received["continue_handler"] = h

            def set_error_callback(self, h):
                received["error_callback"] = h

        registry = AgentRegistry()
        registry.register(TrackingReviewer(name="reviewer"))
        orch = GraphOrchestrator(llm=AsyncMock(), agent_registry=registry)

        sentinel_continue = object()
        sentinel_error = object()
        orch.set_continue_handler(sentinel_continue)
        orch.set_error_callback(sentinel_error)

        await orch._auto_review_node(self._state_with_response())

        assert received.get("continue_handler") is sentinel_continue
        assert received.get("error_callback") is sentinel_error


class TestHandleReviewLoop:
    """Integration tests for the auto-review loop through handle()."""

    @pytest.mark.asyncio
    async def test_no_issues_review_appended_to_response(self):
        """When reviewer finds NO_ISSUES_FOUND, review text is in final response."""
        llm = _make_llm_response("coder", needs_review=True)
        registry = AgentRegistry()
        coder = _MockAgentWithToolCalls(
            name="coder",
            responses=["Implementation complete"],
            tool_calls_per_response=[[_FAKE_TOOL_CALL]],
        )
        reviewer = _MockAgentWithToolCalls(
            name="reviewer",
            responses=["NO_ISSUES_FOUND - all good"],
        )
        registry.register(coder)
        registry.register(reviewer)

        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_review=True)
        response = await orch.handle("add a feature")

        assert "Implementation complete" in response.content
        assert "Auto-Review" in response.content
        assert "NO_ISSUES_FOUND" in response.content

    @pytest.mark.asyncio
    async def test_critical_issue_triggers_fix_pass(self):
        """CRITICAL review causes agent to re-run; second review passes."""
        llm = _make_llm_response("coder", needs_review=True)
        registry = AgentRegistry()
        coder = _MockAgentWithToolCalls(
            name="coder",
            responses=["Initial implementation", "Fixed implementation"],
            tool_calls_per_response=[[_FAKE_TOOL_CALL], [_FAKE_TOOL_CALL]],
        )
        reviewer = _MockAgentWithToolCalls(
            name="reviewer",
            responses=["CRITICAL: SQL injection vulnerability", "NO_ISSUES_FOUND"],
        )
        registry.register(coder)
        registry.register(reviewer)

        orch = GraphOrchestrator(
            llm=llm, agent_registry=registry, auto_review=True, max_review_iterations=2,
        )
        response = await orch.handle("add database query")

        assert coder.call_count == 2   # initial run + fix pass
        assert reviewer.call_count == 2  # first review + second review
        assert "Fixed implementation" in response.content

    @pytest.mark.asyncio
    async def test_auto_review_false_skips_review(self):
        """auto_review=False means reviewer never runs."""
        llm = _make_llm_response("coder", needs_review=True)
        registry = AgentRegistry()
        coder = _MockAgentWithToolCalls(
            name="coder",
            responses=["done"],
            tool_calls_per_response=[[_FAKE_TOOL_CALL]],
        )
        reviewer = _MockAgentWithToolCalls(
            name="reviewer",
            responses=["CRITICAL: something"],
        )
        registry.register(coder)
        registry.register(reviewer)

        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_review=False)
        response = await orch.handle("add feature")

        assert reviewer.call_count == 0
        assert "Auto-Review" not in response.content

    @pytest.mark.asyncio
    async def test_no_tool_calls_skips_review(self):
        """Review is skipped when the agent response has no tool calls."""
        llm = _make_llm_response("coder", needs_review=True)
        registry = AgentRegistry()
        coder = _MockAgentWithToolCalls(
            name="coder",
            responses=["Here is some advice"],
            tool_calls_per_response=[[]],  # no tool calls
        )
        reviewer = _MockAgentWithToolCalls(
            name="reviewer",
            responses=["CRITICAL: something"],
        )
        registry.register(coder)
        registry.register(reviewer)

        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_review=True)
        response = await orch.handle("explain this")

        assert reviewer.call_count == 0
        assert "Auto-Review" not in response.content

    @pytest.mark.asyncio
    async def test_loop_stops_at_max_review_iterations(self):
        """Review loop stops after max_review_iterations even with ongoing CRITICAL issues."""
        llm = _make_llm_response("coder", needs_review=True)
        registry = AgentRegistry()
        coder = _MockAgentWithToolCalls(
            name="coder",
            responses=["v1", "v2", "v3"],
            tool_calls_per_response=[
                [_FAKE_TOOL_CALL], [_FAKE_TOOL_CALL], [_FAKE_TOOL_CALL],
            ],
        )
        reviewer = _MockAgentWithToolCalls(
            name="reviewer",
            responses=["CRITICAL: issue1", "CRITICAL: issue2", "CRITICAL: issue3"],
        )
        registry.register(coder)
        registry.register(reviewer)

        orch = GraphOrchestrator(
            llm=llm, agent_registry=registry, auto_review=True, max_review_iterations=2,
        )
        await orch.handle("add feature")

        # coder: initial run + 1 fix pass (max_review_iterations=2 allows 2 reviews,
        # second review returns "done" because review_iteration >= max)
        assert coder.call_count == 2
        assert reviewer.call_count == 2


class TestExpandedPlanningAgents:
    """_needs_planning triggers for all implementation agents, not just coder."""

    def _state(self, agent: str) -> GraphState:
        return {
            "user_message": "add feature",
            "context": "",
            "selected_agent": agent,
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

    def _make_orch(self, *agents: str) -> GraphOrchestrator:
        llm = AsyncMock()
        registry = _make_registry(*agents)
        return GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)

    def test_architect_triggers_planning(self):
        orch = self._make_orch("architect", "planner")
        assert orch._needs_planning(self._state("architect")) == "plan"

    def test_tester_triggers_planning(self):
        orch = self._make_orch("tester", "planner")
        assert orch._needs_planning(self._state("tester")) == "plan"

    def test_refactor_triggers_planning(self):
        orch = self._make_orch("refactor", "planner")
        assert orch._needs_planning(self._state("refactor")) == "plan"

    def test_debugger_triggers_planning(self):
        orch = self._make_orch("debugger", "planner")
        assert orch._needs_planning(self._state("debugger")) == "plan"

    def test_reviewer_still_skips_planning(self):
        orch = self._make_orch("coder", "planner", "reviewer")
        assert orch._needs_planning(self._state("reviewer")) == "skip"

    def test_researcher_skips_planning(self):
        orch = self._make_orch("coder", "planner", "researcher")
        assert orch._needs_planning(self._state("researcher")) == "skip"


class TestForcePlan:
    """force_plan=True ensures planning runs regardless of router decision."""

    @pytest.mark.asyncio
    async def test_force_plan_overrides_router_false(self):
        """Even if LLM says needs_planning=False, force_plan keeps it True."""
        llm = _make_llm_response("coder", needs_planning=False)
        registry = _make_registry("coder", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)

        state: GraphState = {
            "user_message": "add feature",
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
            "force_plan": True,
        }

        result = await orch._route_node(state)
        assert result["needs_planning"] is True

    @pytest.mark.asyncio
    async def test_force_plan_false_preserves_router_decision(self):
        """Without force_plan, router's needs_planning=False is respected."""
        llm = _make_llm_response("coder", needs_planning=False)
        registry = _make_registry("coder", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)

        state: GraphState = {
            "user_message": "fix typo",
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
            "force_plan": False,
        }

        result = await orch._route_node(state)
        assert result["needs_planning"] is False

    def test_force_plan_bypasses_auto_plan_false(self):
        """force_plan=True runs the planner even when auto_plan=False."""
        llm = AsyncMock()
        registry = _make_registry("coder", "planner")
        # auto_plan=False would normally prevent planning entirely
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
            "force_plan": True,
        }

        assert orch._needs_planning(state) == "plan"

    def test_force_plan_works_for_non_planning_agent(self):
        """force_plan=True plans even when the selected agent is not in _PLANNING_AGENTS."""
        llm = AsyncMock()
        registry = _make_registry("reviewer", "planner")
        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)

        state: GraphState = {
            "user_message": "plan this review",
            "context": "",
            "selected_agent": "reviewer",
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
            "force_plan": True,
        }

        assert orch._needs_planning(state) == "plan"

    @pytest.mark.asyncio
    async def test_handle_force_plan_triggers_planner(self):
        """handle(force_plan=True) causes the planner node to run."""
        llm = _make_llm_response("coder", needs_planning=False)
        registry = AgentRegistry()

        planner_called = []

        class TrackingPlanner(_MockAgent):
            async def run(self, message: str, *, context: str = "") -> AgentResponse:
                planner_called.append(message)
                return AgentResponse(
                    content="## Implementation Plan\nStep 1: do X",
                    iterations=1,
                )

        class ApprovingCoder(_MockAgent):
            async def run(self, message: str, *, context: str = "") -> AgentResponse:
                return AgentResponse(content="coded", iterations=1)

        registry.register(TrackingPlanner(name="planner"))
        registry.register(ApprovingCoder(name="coder"))

        orch = GraphOrchestrator(llm=llm, agent_registry=registry, auto_plan=True)
        # Auto-approve the plan so execution continues
        orch.set_clarification_handler(lambda q, opts, ctx: "Approve")

        await orch.handle("add feature", force_plan=True)

        assert len(planner_called) == 1
        assert "add feature" in planner_called[0]


class TestReviewIterationCount:
    """Reviewer runs exactly max_review_iterations times (no off-by-one)."""

    @pytest.mark.asyncio
    async def test_reviewer_runs_exactly_configured_times(self):
        """With max_review_iterations=2 and persistent CRITICAL issues,
        the reviewer runs exactly 2 times regardless of ongoing problems."""
        llm = _make_llm_response("coder", needs_review=True)
        registry = AgentRegistry()

        reviewer_call_count = 0

        class CountingReviewer(_MockAgent):
            async def run(self, message: str, *, context: str = "") -> AgentResponse:
                nonlocal reviewer_call_count
                reviewer_call_count += 1
                return AgentResponse(
                    content="CRITICAL: persistent issue", iterations=1,
                )

        coder = _MockAgentWithToolCalls(
            name="coder",
            responses=["v1", "v2", "v3"],
            tool_calls_per_response=[
                [_FAKE_TOOL_CALL], [_FAKE_TOOL_CALL], [_FAKE_TOOL_CALL],
            ],
        )
        registry.register(coder)
        registry.register(CountingReviewer(name="reviewer"))

        orch = GraphOrchestrator(
            llm=llm, agent_registry=registry,
            auto_review=True, max_review_iterations=2,
        )
        await orch.handle("add feature")

        assert reviewer_call_count == 2

    @pytest.mark.asyncio
    async def test_reviewer_runs_exactly_1_when_max_is_1(self):
        """max_review_iterations=1 means the reviewer runs exactly once."""
        llm = _make_llm_response("coder", needs_review=True)
        registry = AgentRegistry()
        reviewer_call_count = 0

        class CountingReviewer(_MockAgent):
            async def run(self, message: str, *, context: str = "") -> AgentResponse:
                nonlocal reviewer_call_count
                reviewer_call_count += 1
                return AgentResponse(content="CRITICAL: bad code", iterations=1)

        coder = _MockAgentWithToolCalls(
            name="coder",
            responses=["v1", "v2"],
            tool_calls_per_response=[[_FAKE_TOOL_CALL], [_FAKE_TOOL_CALL]],
        )
        registry.register(coder)
        registry.register(CountingReviewer(name="reviewer"))

        orch = GraphOrchestrator(
            llm=llm, agent_registry=registry,
            auto_review=True, max_review_iterations=1,
        )
        await orch.handle("add feature")

        assert reviewer_call_count == 1

    @pytest.mark.asyncio
    async def test_no_infinite_loop_when_reviewer_always_times_out(self):
        """Reviewer that always times out must not loop forever."""
        import asyncio as _asyncio
        llm = _make_llm_response("coder", needs_review=True)
        registry = AgentRegistry()

        class TimeoutReviewer(_MockAgent):
            async def run(self, message: str, *, context: str = "") -> AgentResponse:
                raise _asyncio.TimeoutError

        coder = _MockAgentWithToolCalls(
            name="coder",
            responses=["v1", "v2"],
            tool_calls_per_response=[[_FAKE_TOOL_CALL], [_FAKE_TOOL_CALL]],
        )
        registry.register(coder)
        registry.register(TimeoutReviewer(name="reviewer"))

        orch = GraphOrchestrator(
            llm=llm, agent_registry=registry,
            auto_review=True, max_review_iterations=2, agent_timeout=0,
        )
        # Must complete without hanging
        response = await orch.handle("add feature")
        assert response is not None
