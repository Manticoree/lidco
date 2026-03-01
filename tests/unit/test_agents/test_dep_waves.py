"""Tests for _build_dep_waves() and dependency-aware _execute_parallel_node."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.base import AgentResponse, TokenUsage
from lidco.agents.graph import GraphOrchestrator
from lidco.agents.registry import AgentRegistry


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_orch() -> GraphOrchestrator:
    llm = MagicMock()
    reg = AgentRegistry()
    return GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)


def _make_plan_response(content: str) -> AgentResponse:
    return AgentResponse(
        content=content,
        tool_calls_made=[],
        iterations=1,
        model_used="test",
        token_usage=TokenUsage(total_tokens=10, total_cost_usd=0.001),
    )


def _dummy_response(label: str = "ok") -> AgentResponse:
    return AgentResponse(
        content=label,
        tool_calls_made=[],
        iterations=1,
        model_used="test",
        token_usage=TokenUsage(total_tokens=5, total_cost_usd=0.0),
    )


# ── TestBuildDepWaves ─────────────────────────────────────────────────────────


class TestBuildDepWaves:
    def test_no_deps_single_wave(self):
        """Steps with no relevant deps → one wave containing all steps."""
        steps = ["A", "B", "C"]
        deps = {1: [], 2: [], 3: []}
        all_steps = ["A", "B", "C"]
        waves = GraphOrchestrator._build_dep_waves(steps, deps, all_steps)
        assert len(waves) == 1
        assert set(waves[0]) == {"A", "B", "C"}

    def test_linear_deps_sequential_waves(self):
        """A → B → C produces three single-step waves."""
        steps = ["A", "B", "C"]
        deps = {1: [], 2: [1], 3: [2]}
        all_steps = ["A", "B", "C"]
        waves = GraphOrchestrator._build_dep_waves(steps, deps, all_steps)
        assert len(waves) == 3
        assert waves[0] == ["A"]
        assert waves[1] == ["B"]
        assert waves[2] == ["C"]

    def test_independent_steps_single_wave(self):
        """Two steps with no deps on each other → single wave."""
        steps = ["X", "Y"]
        deps = {1: [], 2: []}
        all_steps = ["X", "Y"]
        waves = GraphOrchestrator._build_dep_waves(steps, deps, all_steps)
        assert len(waves) == 1
        assert set(waves[0]) == {"X", "Y"}

    def test_diamond_pattern(self):
        """Steps A,B → C → D gives waves [A,B], [C], [D]."""
        steps = ["A", "B", "C", "D"]
        deps = {1: [], 2: [], 3: [1, 2], 4: [3]}
        all_steps = ["A", "B", "C", "D"]
        waves = GraphOrchestrator._build_dep_waves(steps, deps, all_steps)
        assert len(waves) == 3
        assert set(waves[0]) == {"A", "B"}
        assert waves[1] == ["C"]
        assert waves[2] == ["D"]

    def test_empty_parallel_steps(self):
        """Empty input → empty output."""
        waves = GraphOrchestrator._build_dep_waves([], {1: []}, ["A"])
        assert waves == []

    def test_empty_plan_step_deps_single_wave(self):
        """No deps dict → fall back to single wave."""
        steps = ["A", "B"]
        waves = GraphOrchestrator._build_dep_waves(steps, {}, ["A", "B"])
        assert waves == [["A", "B"]]

    def test_empty_all_steps_single_wave(self):
        """No all_steps → can't map, fall back to single wave."""
        steps = ["A", "B"]
        waves = GraphOrchestrator._build_dep_waves(steps, {1: [], 2: [1]}, [])
        assert waves == [["A", "B"]]

    def test_cycle_fallback_single_wave(self):
        """Cycle A→B, B→A → cycle detected, all dumped in one wave."""
        steps = ["A", "B"]
        deps = {1: [2], 2: [1]}
        all_steps = ["A", "B"]
        waves = GraphOrchestrator._build_dep_waves(steps, deps, all_steps)
        assert len(waves) == 1
        assert set(waves[0]) == {"A", "B"}

    def test_dep_outside_parallel_set_ignored(self):
        """Dep on a step that is NOT in parallel_steps is treated as satisfied."""
        # Steps 2 and 4 are parallel; they both dep on step 1 which is sequential
        steps = ["Do B", "Do D"]
        deps = {1: [], 2: [1], 4: [1]}
        all_steps = ["Do A", "Do B", "Wire up", "Do D", "Finalize"]
        waves = GraphOrchestrator._build_dep_waves(steps, deps, all_steps)
        # Step 1 is outside parallel_set → both steps have no relevant deps → single wave
        assert len(waves) == 1
        assert set(waves[0]) == {"Do B", "Do D"}

    def test_parallel_marker_stripped_in_mapping(self):
        """Steps with [PARALLEL] marker in all_steps are correctly matched."""
        steps = ["Do B", "Do D"]
        deps = {1: [], 2: [], 3: [2], 4: []}  # step 3 deps on step 2
        all_steps = ["Do A", "Do B  [PARALLEL]", "Do C", "Do D  [PARALLEL]"]
        # Steps 2 and 4 are parallel; step 3 is NOT in parallel set, so its dep is irrelevant
        waves = GraphOrchestrator._build_dep_waves(steps, deps, all_steps)
        assert len(waves) == 1
        assert set(waves[0]) == {"Do B", "Do D"}

    def test_wave_order_respects_deps(self):
        """Steps respecting deps appear in later waves than their dependencies."""
        steps = ["Alpha", "Beta", "Gamma"]
        deps = {1: [], 2: [1], 3: [1]}
        all_steps = ["Alpha", "Beta", "Gamma"]
        waves = GraphOrchestrator._build_dep_waves(steps, deps, all_steps)
        # Alpha must be in an earlier wave than Beta and Gamma
        alpha_wave = next(i for i, w in enumerate(waves) if "Alpha" in w)
        beta_wave = next(i for i, w in enumerate(waves) if "Beta" in w)
        gamma_wave = next(i for i, w in enumerate(waves) if "Gamma" in w)
        assert alpha_wave < beta_wave
        assert alpha_wave < gamma_wave


# ── TestApproveNodeStoresDeps ─────────────────────────────────────────────────


class TestApproveNodeStoresDeps:
    _PLAN_WITH_DEPS = (
        "**Steps:**\n"
        "1. Do A\n"
        "   Deps: none\n"
        "2. Do B  [PARALLEL]\n"
        "   Deps: 1\n"
        "3. Wire up\n"
        "   Deps: 1, 2\n"
    )

    _PLAN_NO_DEPS = "1. Step one\n2. Step two\n"

    def test_plan_step_deps_stored_on_auto_approve(self):
        """After auto-approve, state contains plan_step_deps dict."""
        orch = _make_orch()
        state = {
            "user_message": "feat",
            "context": "",
            "plan_response": _make_plan_response(self._PLAN_WITH_DEPS),
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(state))
        deps = result.get("plan_step_deps")
        assert isinstance(deps, dict)
        # Step 2 deps on step 1
        assert deps.get(2) == [1]
        # Step 3 deps on steps 1 and 2
        assert set(deps.get(3, [])) == {1, 2}

    def test_no_deps_lines_stores_empty_or_default_dict(self):
        """Plan without Deps: lines stores an empty or all-empty-list dict."""
        orch = _make_orch()
        state = {
            "user_message": "feat",
            "context": "",
            "plan_response": _make_plan_response(self._PLAN_NO_DEPS),
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        with patch.object(orch, "_save_approved_plan"):
            result = asyncio.run(orch._approve_plan_node(state))
        deps = result.get("plan_step_deps")
        assert isinstance(deps, dict)
        # All dep lists should be empty (no Deps: lines → no dep nums)
        assert all(v == [] for v in deps.values())

    def test_rejection_stores_none(self):
        """Plan rejection → plan_step_deps is None."""
        orch = _make_orch()
        orch._clarification_handler = lambda p, c, ctx: "Reject"
        state = {
            "user_message": "feat",
            "context": "",
            "plan_response": _make_plan_response(self._PLAN_WITH_DEPS),
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._approve_plan_node(state))
        assert result.get("plan_step_deps") is None

    def test_none_plan_response_stores_none(self):
        """No plan_response → plan_step_deps is None."""
        orch = _make_orch()
        state = {
            "user_message": "feat",
            "context": "",
            "plan_response": None,
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._approve_plan_node(state))
        assert result.get("plan_step_deps") is None


# ── TestParallelNodeWaveExecution ─────────────────────────────────────────────


_PLAN_TWO_DEP_WAVES = (
    "1. Alpha\n"
    "   Deps: none\n"
    "2. Beta  [PARALLEL]\n"
    "   Deps: none\n"
    "3. Gamma  [PARALLEL]\n"
    "   Deps: 2\n"  # Gamma waits for Beta
)


def _make_parallel_state(plan_content: str, parallel_steps: list[str], deps: dict) -> dict:
    return {
        "user_message": "do work",
        "context": "",
        "selected_agent": "coder",
        "plan_response": _make_plan_response(plan_content),
        "parallel_steps": parallel_steps,
        "plan_step_deps": deps,
        "accumulated_tokens": 0,
        "accumulated_cost_usd": 0.0,
    }


class TestParallelNodeWaveExecution:
    def test_single_wave_all_at_once(self):
        """When all steps are independent, they run in one gather call."""
        plan = "1. A\n   Deps: none\n2. B  [PARALLEL]\n   Deps: none\n"
        orch = _make_orch()

        # Register a dummy coder agent
        coder = MagicMock()
        coder.name = "coder"
        coder.config = MagicMock()
        coder.config.name = "coder"
        coder.clone = lambda: coder
        for m in ("set_status_callback", "set_permission_handler", "set_token_callback",
                  "set_continue_handler", "set_clarification_handler", "set_stream_callback",
                  "set_tool_event_callback", "set_error_callback"):
            setattr(coder, m, MagicMock())
        coder.run = AsyncMock(return_value=_dummy_response("done"))
        orch._registry._agents["coder"] = coder

        state = _make_parallel_state(plan, ["B", "C"], {1: [], 2: [], 3: []})
        result = asyncio.run(orch._execute_parallel_node(state))
        assert result.get("error") is None

    def test_wave_annotation_in_multi_wave_content(self):
        """With multiple waves, merged content contains [wave N] annotation."""
        orch = _make_orch()

        call_order: list[str] = []

        async def fake_run(message: str, context: str = "") -> AgentResponse:
            step = message.split("[PARALLEL STEP]: ")[-1].strip()
            call_order.append(step)
            return _dummy_response(f"result:{step}")

        coder = MagicMock()
        coder.name = "coder"
        coder.config = MagicMock()
        coder.config.name = "coder"
        coder.clone = lambda: coder
        for m in ("set_status_callback", "set_permission_handler", "set_token_callback",
                  "set_continue_handler", "set_clarification_handler", "set_stream_callback",
                  "set_tool_event_callback", "set_error_callback"):
            setattr(coder, m, MagicMock())
        coder.run = fake_run
        orch._registry._agents["coder"] = coder

        # Beta has no deps; Gamma depends on Beta → two waves
        state = _make_parallel_state(
            _PLAN_TWO_DEP_WAVES,
            ["Beta", "Gamma"],
            {1: [], 2: [], 3: [2]},
        )
        result = asyncio.run(orch._execute_parallel_node(state))
        content = result["agent_response"].content
        assert "[wave 1]" in content
        assert "[wave 2]" in content

    def test_beta_runs_before_gamma(self):
        """Gamma (dep on Beta) must be called after Beta completes."""
        orch = _make_orch()

        call_order: list[str] = []

        async def fake_run(message: str, context: str = "") -> AgentResponse:
            step = message.split("[PARALLEL STEP]: ")[-1].strip()
            call_order.append(step)
            return _dummy_response()

        coder = MagicMock()
        coder.name = "coder"
        coder.config = MagicMock()
        coder.config.name = "coder"
        coder.clone = lambda: coder
        for m in ("set_status_callback", "set_permission_handler", "set_token_callback",
                  "set_continue_handler", "set_clarification_handler", "set_stream_callback",
                  "set_tool_event_callback", "set_error_callback"):
            setattr(coder, m, MagicMock())
        coder.run = fake_run
        orch._registry._agents["coder"] = coder

        state = _make_parallel_state(
            _PLAN_TWO_DEP_WAVES,
            ["Beta", "Gamma"],
            {1: [], 2: [], 3: [2]},
        )
        asyncio.run(orch._execute_parallel_node(state))
        # Beta (step 2, no deps) must be called before Gamma (step 3, dep on 2)
        assert call_order.index("Beta") < call_order.index("Gamma")

    def test_no_plan_step_deps_falls_back_to_single_wave(self):
        """When plan_step_deps not in state, all steps run in one wave."""
        orch = _make_orch()

        coder = MagicMock()
        coder.name = "coder"
        coder.config = MagicMock()
        coder.config.name = "coder"
        coder.clone = lambda: coder
        for m in ("set_status_callback", "set_permission_handler", "set_token_callback",
                  "set_continue_handler", "set_clarification_handler", "set_stream_callback",
                  "set_tool_event_callback", "set_error_callback"):
            setattr(coder, m, MagicMock())
        coder.run = AsyncMock(return_value=_dummy_response())
        orch._registry._agents["coder"] = coder

        state = {
            "user_message": "task",
            "context": "",
            "selected_agent": "coder",
            "plan_response": _make_plan_response("1. A\n2. B\n"),
            "parallel_steps": ["A", "B"],
            # plan_step_deps deliberately absent
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._execute_parallel_node(state))
        assert result.get("error") is None
        # Both steps appear in merged content
        assert "A" in result["agent_response"].content
        assert "B" in result["agent_response"].content

    def test_status_callback_per_wave(self):
        """Status callback is fired for each wave when multiple waves exist."""
        orch = _make_orch()
        status_calls: list[str] = []
        orch.set_status_callback(lambda s: status_calls.append(s))

        coder = MagicMock()
        coder.name = "coder"
        coder.config = MagicMock()
        coder.config.name = "coder"
        coder.clone = lambda: coder
        for m in ("set_status_callback", "set_permission_handler", "set_token_callback",
                  "set_continue_handler", "set_clarification_handler", "set_stream_callback",
                  "set_tool_event_callback", "set_error_callback"):
            setattr(coder, m, MagicMock())
        coder.run = AsyncMock(return_value=_dummy_response())
        orch._registry._agents["coder"] = coder

        state = _make_parallel_state(
            _PLAN_TWO_DEP_WAVES,
            ["Beta", "Gamma"],
            {1: [], 2: [], 3: [2]},
        )
        asyncio.run(orch._execute_parallel_node(state))
        wave_calls = [s for s in status_calls if "Wave" in s or "wave" in s]
        assert len(wave_calls) >= 2
