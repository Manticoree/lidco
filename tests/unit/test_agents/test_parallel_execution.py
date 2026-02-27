"""Tests for parallel agent execution in GraphOrchestrator."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.agents.base import AgentConfig, AgentResponse, BaseAgent, TokenUsage
from lidco.agents.graph import GraphOrchestrator, GraphState
from lidco.agents.registry import AgentRegistry


# ─── test doubles ───────────────────────────────────────────────────────────

def _make_config(name: str = "coder") -> AgentConfig:
    return AgentConfig(name=name, description=f"{name} agent", system_prompt="test")


class _TrackingAgent(BaseAgent):
    """A real BaseAgent subclass that tracks calls and returns preset responses.

    Using a real subclass ensures that ``type(agent)(config, llm, registry)``
    in ``_execute_parallel_node`` creates a correct fresh instance.
    """

    call_count: int = 0  # shared across all instances via class var
    preset_content: str = "response"
    preset_tokens: int = 100

    def get_system_prompt(self) -> str:
        return "test"

    async def run(self, user_message: str, context: str = "") -> AgentResponse:
        _TrackingAgent.call_count += 1
        return AgentResponse(
            content=_TrackingAgent.preset_content,
            iterations=1,
            token_usage=TokenUsage(
                total_tokens=_TrackingAgent.preset_tokens,
                total_cost_usd=0.001,
            ),
        )


def _reset_tracking() -> None:
    _TrackingAgent.call_count = 0
    _TrackingAgent.preset_content = "response"
    _TrackingAgent.preset_tokens = 100


def _make_tracking_agent(name: str = "coder") -> _TrackingAgent:
    return _TrackingAgent(
        config=_make_config(name),
        llm=MagicMock(),
        tool_registry=MagicMock(),
    )


def _make_registry(*names: str) -> AgentRegistry:
    registry = AgentRegistry()
    for name in names:
        registry.register(_make_tracking_agent(name))
    return registry


def _make_orch(registry: AgentRegistry | None = None, max_parallel: int = 3) -> GraphOrchestrator:
    if registry is None:
        registry = _make_registry("coder")
    return GraphOrchestrator(
        llm=AsyncMock(),
        agent_registry=registry,
        max_parallel_agents=max_parallel,
    )


def _parallel_state(parallel_steps: list[str], agent_name: str = "coder") -> GraphState:
    return {  # type: ignore[return-value]
        "user_message": "do something",
        "context": "",
        "selected_agent": agent_name,
        "agent_response": None,
        "conversation_history": [],
        "needs_review": False,
        "review_response": None,
        "error": None,
        "iteration": 0,
        "clarification_context": "",
        "needs_planning": False,
        "plan_response": None,
        "plan_approved": True,
        "review_iteration": 0,
        "force_plan": False,
        "accumulated_tokens": 0,
        "accumulated_cost_usd": 0.0,
        "medium_issues": "",
        "parallel_steps": parallel_steps,
    }


# ─── _parse_parallel_steps ──────────────────────────────────────────────────

class TestParseParallelSteps:
    def test_no_parallel_markers_returns_empty(self):
        plan = "1. Do thing A\n2. Do thing B\n3. Do thing C"
        assert GraphOrchestrator._parse_parallel_steps(plan) == []

    def test_single_parallel_step(self):
        plan = "1. Do thing A  [PARALLEL]\n2. Do thing B"
        steps = GraphOrchestrator._parse_parallel_steps(plan)
        assert len(steps) == 1
        assert "Do thing A" in steps[0]

    def test_two_parallel_steps(self):
        plan = (
            "1. Do thing A  [PARALLEL]\n"
            "2. Do thing B  [PARALLEL]\n"
            "3. Do thing C\n"
        )
        steps = GraphOrchestrator._parse_parallel_steps(plan)
        assert len(steps) == 2

    def test_case_insensitive_marker(self):
        plan = "1. Write tests  [parallel]\n"
        steps = GraphOrchestrator._parse_parallel_steps(plan)
        assert len(steps) == 1
        assert "Write tests" in steps[0]

    def test_leading_numbering_stripped(self):
        plan = "1. Update auth.py  [PARALLEL]\n"
        steps = GraphOrchestrator._parse_parallel_steps(plan)
        assert "Update auth.py" in steps[0]

    def test_original_case_preserved(self):
        plan = "1. Update AuthService  [PARALLEL]\n"
        steps = GraphOrchestrator._parse_parallel_steps(plan)
        assert "AuthService" in steps[0]

    def test_empty_plan_returns_empty(self):
        assert GraphOrchestrator._parse_parallel_steps("") == []

    def test_bullet_prefixes_stripped(self):
        plan = "- Write migration  [PARALLEL]\n"
        steps = GraphOrchestrator._parse_parallel_steps(plan)
        assert len(steps) == 1
        assert steps[0].startswith("Write migration")

    def test_multiple_non_adjacent_groups_all_parsed(self):
        plan = (
            "1. Step A  [PARALLEL]\n"
            "2. Step B\n"
            "3. Step C  [PARALLEL]\n"
        )
        steps = GraphOrchestrator._parse_parallel_steps(plan)
        assert len(steps) == 2


# ─── _plan_approved routing ─────────────────────────────────────────────────

class TestPlanApprovedRouting:
    def _state(self, approved: bool, parallel_steps: list[str] | None = None) -> GraphState:
        return {  # type: ignore[return-value]
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
            "needs_planning": False,
            "plan_response": None,
            "plan_approved": approved,
            "review_iteration": 0,
            "force_plan": False,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
            "medium_issues": "",
            "parallel_steps": parallel_steps or [],
        }

    def test_approved_no_parallel_returns_sequential(self):
        orch = _make_orch()
        state = self._state(approved=True, parallel_steps=[])
        assert orch._plan_approved(state) == "sequential"

    def test_approved_with_parallel_returns_parallel(self):
        orch = _make_orch()
        state = self._state(approved=True, parallel_steps=["step A", "step B"])
        assert orch._plan_approved(state) == "parallel"

    def test_rejected_returns_rejected(self):
        orch = _make_orch()
        state = self._state(approved=False)
        assert orch._plan_approved(state) == "rejected"

    def test_rejected_ignores_parallel_steps(self):
        orch = _make_orch()
        state = self._state(approved=False, parallel_steps=["step A"])
        assert orch._plan_approved(state) == "rejected"


# ─── _execute_parallel_node ─────────────────────────────────────────────────

class TestExecuteParallelNode:
    def setup_method(self):
        _reset_tracking()

    @pytest.mark.asyncio
    async def test_merges_content_from_all_steps(self):
        registry = _make_registry("coder")
        orch = _make_orch(registry)
        _TrackingAgent.preset_content = "step result"

        state = _parallel_state(["step A", "step B"])
        result = await orch._execute_parallel_node(state)

        assert result["error"] is None
        resp = result["agent_response"]
        assert resp is not None
        assert "Parallel Step 1" in resp.content
        assert "Parallel Step 2" in resp.content
        assert "step result" in resp.content

    @pytest.mark.asyncio
    async def test_missing_agent_returns_error_state(self):
        orch = _make_orch(_make_registry())  # empty registry
        state = _parallel_state(["step A"], agent_name="ghost")
        result = await orch._execute_parallel_node(state)
        assert result["error"] is not None
        assert result["agent_response"] is not None
        assert "ghost" in result["agent_response"].content

    @pytest.mark.asyncio
    async def test_max_parallel_cap_limits_concurrency(self):
        """All steps execute, but concurrency is capped at max_parallel_agents.

        The semaphore limits how many steps run simultaneously, but does NOT
        drop any steps from the plan (P2-02 fix: truncation removed).
        """
        registry = _make_registry("coder")
        orch = _make_orch(registry, max_parallel=2)

        # 5 steps — all 5 should execute (semaphore limits concurrency, not count)
        state = _parallel_state(["s1", "s2", "s3", "s4", "s5"])
        result = await orch._execute_parallel_node(state)

        assert _TrackingAgent.call_count == 5
        resp = result["agent_response"]
        assert resp is not None
        # All 5 step headers should appear
        assert "Parallel Step 1" in resp.content
        assert "Parallel Step 5" in resp.content

    @pytest.mark.asyncio
    async def test_tokens_accumulated_from_all_steps(self):
        registry = _make_registry("coder")
        orch = _make_orch(registry)
        _TrackingAgent.preset_tokens = 150  # each step returns 150 tokens

        state = _parallel_state(["step A", "step B"])
        state["accumulated_tokens"] = 0  # type: ignore[typeddict-item]

        result = await orch._execute_parallel_node(state)
        # 2 steps × 150 tokens each = 300
        assert result["accumulated_tokens"] == 300

    @pytest.mark.asyncio
    async def test_tool_calls_merged_from_all_steps(self):
        """Tool calls from all parallel steps are unioned into one list."""
        registry = _make_registry("coder")
        orch = _make_orch(registry)

        # Override run to return tool calls
        orig_run = _TrackingAgent.run

        async def _run_with_calls(self, user_message, context=""):
            call_n = _TrackingAgent.call_count
            _TrackingAgent.call_count += 1
            return AgentResponse(
                content="done",
                iterations=1,
                token_usage=TokenUsage(total_tokens=10),
                tool_calls_made=[{"tool": "file_write", "args": {"n": call_n}}],
            )

        _TrackingAgent.run = _run_with_calls  # type: ignore[method-assign]
        try:
            state = _parallel_state(["step A", "step B"])
            result = await orch._execute_parallel_node(state)
            resp = result["agent_response"]
            assert resp is not None
            assert len(resp.tool_calls_made) == 2
        finally:
            _TrackingAgent.run = orig_run  # type: ignore[method-assign]

    @pytest.mark.asyncio
    async def test_no_steps_returns_empty_response(self):
        registry = _make_registry("coder")
        orch = _make_orch(registry)

        state = _parallel_state([])
        result = await orch._execute_parallel_node(state)

        assert result["error"] is None
        resp = result["agent_response"]
        assert resp is not None
        assert resp.content == ""
        assert _TrackingAgent.call_count == 0


# ─── parse + routing integration ────────────────────────────────────────────

class TestParallelIntegration:
    """End-to-end: parse plan → detect parallel → route to execute_parallel."""

    def test_plan_with_parallel_routes_to_parallel_node(self):
        orch = _make_orch()
        plan_content = (
            "**Steps:**\n"
            "1. [Easy] `src/a.py` — do A  [PARALLEL]\n"
            "2. [Easy] `src/b.py` — do B  [PARALLEL]\n"
            "3. [Hard] `src/c.py` — do C\n"
        )
        steps = GraphOrchestrator._parse_parallel_steps(plan_content)
        assert len(steps) == 2

        state: GraphState = {  # type: ignore[assignment]
            "user_message": "x",
            "context": "",
            "selected_agent": "coder",
            "plan_approved": True,
            "parallel_steps": steps,
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "review_iteration": 0,
            "force_plan": False,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
            "medium_issues": "",
        }
        assert orch._plan_approved(state) == "parallel"

    def test_plan_without_parallel_routes_sequential(self):
        orch = _make_orch()
        plan_content = "1. Do A\n2. Do B\n3. Do C\n"
        steps = GraphOrchestrator._parse_parallel_steps(plan_content)
        assert steps == []

        state: GraphState = {  # type: ignore[assignment]
            "user_message": "x",
            "context": "",
            "selected_agent": "coder",
            "plan_approved": True,
            "parallel_steps": steps,
            "agent_response": None,
            "conversation_history": [],
            "needs_review": False,
            "review_response": None,
            "error": None,
            "iteration": 0,
            "clarification_context": "",
            "needs_planning": False,
            "plan_response": None,
            "review_iteration": 0,
            "force_plan": False,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
            "medium_issues": "",
        }
        assert orch._plan_approved(state) == "sequential"

    def test_max_parallel_agents_config(self):
        """Config is passed through to the orchestrator."""
        orch = GraphOrchestrator(
            llm=AsyncMock(),
            agent_registry=AgentRegistry(),
            max_parallel_agents=5,
        )
        assert orch._max_parallel_agents == 5
