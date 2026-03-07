"""Tests for T88 — Multi-hypothesis ranking and T93 compilation fast-path."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.agents.base import AgentConfig, AgentResponse, BaseAgent, TokenUsage
from lidco.agents.graph import GraphOrchestrator, _FAST_PATH_ERROR_TYPES
from lidco.agents.registry import AgentRegistry
from lidco.llm.base import LLMResponse


# ── helpers ──────────────────────────────────────────────────────────────────


class ConcreteAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        return self._config.system_prompt


def _make_agent(name: str) -> ConcreteAgent:
    config = AgentConfig(
        name=name,
        description=name,
        system_prompt="You are helpful.",
        tools=[],
        max_iterations=1,
    )
    llm = MagicMock()
    llm.complete = AsyncMock(
        return_value=LLMResponse(
            content="done", model="m", tool_calls=[], usage={}, finish_reason="stop"
        )
    )
    registry = MagicMock()
    registry.list_tools.return_value = []
    return ConcreteAgent(config=config, llm=llm, tool_registry=registry)


def _make_orch() -> GraphOrchestrator:
    llm = MagicMock()
    llm.complete = AsyncMock(
        return_value=LLMResponse(
            content='{"agent": "debugger", "needs_review": false, "needs_planning": false}',
            model="m",
            tool_calls=[],
            usage={},
            finish_reason="stop",
        )
    )
    reg = AgentRegistry()
    reg.register(_make_agent("debugger"))
    orch = GraphOrchestrator(llm=llm, agent_registry=reg, auto_review=False, auto_plan=False)
    return orch


# ── setter tests ──────────────────────────────────────────────────────────────


class TestNewSetters:
    def test_set_debug_hypothesis_default_true(self):
        orch = _make_orch()
        assert orch._debug_hypothesis_enabled is True

    def test_set_debug_hypothesis_false(self):
        orch = _make_orch()
        orch.set_debug_hypothesis(False)
        assert orch._debug_hypothesis_enabled is False

    def test_set_debug_fast_path_default_true(self):
        orch = _make_orch()
        assert orch._debug_fast_path_enabled is True

    def test_set_debug_fast_path_false(self):
        orch = _make_orch()
        orch.set_debug_fast_path(False)
        assert orch._debug_fast_path_enabled is False

    def test_set_auto_debug_default_false(self):
        orch = _make_orch()
        assert orch._auto_debug_enabled is False

    def test_set_auto_debug_true(self):
        orch = _make_orch()
        orch.set_auto_debug(True)
        assert orch._auto_debug_enabled is True

    def test_set_fix_memory_stores(self):
        orch = _make_orch()
        mock_fm = MagicMock()
        orch.set_fix_memory(mock_fm)
        assert orch._fix_memory is mock_fm

    def test_set_error_ledger_stores(self):
        orch = _make_orch()
        mock_ledger = MagicMock()
        orch.set_error_ledger(mock_ledger)
        assert orch._error_ledger is mock_ledger


# ── debug preset tests ────────────────────────────────────────────────────────


class TestDebugPresets:
    def test_preset_fast(self):
        orch = _make_orch()
        orch.set_debug_preset("fast")
        assert orch._debug_hypothesis_enabled is True
        assert orch._debug_fast_path_enabled is True
        assert orch._auto_debug_enabled is False

    def test_preset_balanced(self):
        orch = _make_orch()
        orch.set_debug_preset("balanced")
        assert orch._debug_hypothesis_enabled is True
        assert orch._debug_fast_path_enabled is True
        assert orch._auto_debug_enabled is False

    def test_preset_thorough(self):
        orch = _make_orch()
        orch.set_debug_preset("thorough")
        assert orch._debug_hypothesis_enabled is True
        assert orch._debug_fast_path_enabled is False
        assert orch._auto_debug_enabled is True

    def test_preset_silent(self):
        orch = _make_orch()
        orch.set_debug_preset("silent")
        assert orch._debug_hypothesis_enabled is False
        assert orch._debug_fast_path_enabled is True
        assert orch._auto_debug_enabled is False

    def test_unknown_preset_sets_name_but_not_flags(self):
        orch = _make_orch()
        orch.set_debug_preset("unknown_preset")
        # Flags unchanged from defaults
        assert orch._debug_hypothesis_enabled is True


# ── hypothesis generation tests ───────────────────────────────────────────────


class TestGenerateHypotheses:
    def test_disabled_returns_empty(self):
        orch = _make_orch()
        orch.set_debug_hypothesis(False)
        result = asyncio.run(orch._generate_hypotheses("error ctx", "task ctx"))
        assert result == ""

    def test_returns_hypotheses_section_on_success(self):
        orch = _make_orch()
        orch._llm.complete = AsyncMock(
            return_value=LLMResponse(
                content="H1 [HIGH]: Some root cause\n  First check: grep session.py",
                model="m",
                tool_calls=[],
                usage={},
                finish_reason="stop",
            )
        )
        result = asyncio.run(orch._generate_hypotheses("error ctx", "task ctx"))
        assert "## Debug Hypotheses" in result

    def test_insufficient_context_returns_empty(self):
        orch = _make_orch()
        orch._llm.complete = AsyncMock(
            return_value=LLMResponse(
                content="INSUFFICIENT_CONTEXT",
                model="m",
                tool_calls=[],
                usage={},
                finish_reason="stop",
            )
        )
        result = asyncio.run(orch._generate_hypotheses("", ""))
        assert result == ""

    def test_timeout_returns_empty(self):
        import asyncio as _asyncio

        orch = _make_orch()

        async def _timeout(*a, **kw):
            raise _asyncio.TimeoutError()

        orch._llm.complete = _timeout
        result = asyncio.run(orch._generate_hypotheses("error ctx", "task"))
        assert result == ""

    def test_exception_returns_empty(self):
        orch = _make_orch()

        async def _fail(*a, **kw):
            raise RuntimeError("LLM down")

        orch._llm.complete = _fail
        result = asyncio.run(orch._generate_hypotheses("error ctx", "task"))
        assert result == ""

    def test_empty_llm_response_returns_empty(self):
        orch = _make_orch()
        orch._llm.complete = AsyncMock(
            return_value=LLMResponse(
                content="", model="m", tool_calls=[], usage={}, finish_reason="stop"
            )
        )
        result = asyncio.run(orch._generate_hypotheses("error ctx", "task"))
        assert result == ""


# ── compilation fast-path tests ───────────────────────────────────────────────


class TestCompilationFastPath:
    def test_fast_path_error_types_set(self):
        assert "SyntaxError" in _FAST_PATH_ERROR_TYPES
        assert "ImportError" in _FAST_PATH_ERROR_TYPES
        assert "NameError" in _FAST_PATH_ERROR_TYPES
        assert "ModuleNotFoundError" in _FAST_PATH_ERROR_TYPES

    def test_disabled_returns_false(self):
        orch = _make_orch()
        orch.set_debug_fast_path(False)
        result = asyncio.run(
            orch._try_compilation_fast_path("error ctx", "file.py", "SyntaxError")
        )
        assert result is False

    def test_non_fast_path_error_returns_false(self):
        orch = _make_orch()
        result = asyncio.run(
            orch._try_compilation_fast_path("error ctx", "file.py", "AttributeError")
        )
        assert result is False

    def test_no_file_hint_returns_false(self):
        orch = _make_orch()
        result = asyncio.run(
            orch._try_compilation_fast_path("error ctx", None, "SyntaxError")
        )
        assert result is False

    def test_fast_path_syntax_error_returns_false(self):
        # Current implementation is a stub that always returns False
        orch = _make_orch()
        result = asyncio.run(
            orch._try_compilation_fast_path("error ctx", "some/file.py", "SyntaxError")
        )
        assert result is False


# ── hypothesis injected into debugger agent ───────────────────────────────────


class TestHypothesisInjectionIntoDebugger:
    def test_hypothesis_injected_when_enabled(self):
        orch = _make_orch()
        orch.set_debug_hypothesis(True)
        orch.set_error_summary_builder(lambda: "## Recent Errors\n- AttributeError")

        # Mock hypothesis LLM call
        orch._llm.complete = AsyncMock(
            return_value=LLMResponse(
                content="H1 [HIGH]: Missing None check",
                model="m",
                tool_calls=[],
                usage={},
                finish_reason="stop",
            )
        )

        agent = orch._registry.get("debugger")
        captured: list[str] = []
        original = agent.prepend_system_context

        def _capture(text: str) -> None:
            captured.append(text)
            original(text)

        agent.prepend_system_context = _capture  # type: ignore

        state = {
            "user_message": "debug this",
            "context": "",
            "selected_agent": "debugger",
            "review_iteration": 0,
            "conversation_history": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        asyncio.run(orch._execute_agent_node(state))
        assert any("Debug Hypotheses" in t for t in captured)

    def test_hypothesis_not_injected_when_disabled(self):
        orch = _make_orch()
        orch.set_debug_hypothesis(False)
        orch.set_error_summary_builder(lambda: "## Recent Errors\n- AttributeError")

        agent = orch._registry.get("debugger")
        captured: list[str] = []
        original = agent.prepend_system_context

        def _capture(text: str) -> None:
            captured.append(text)
            original(text)

        agent.prepend_system_context = _capture  # type: ignore

        state = {
            "user_message": "debug this",
            "context": "",
            "selected_agent": "debugger",
            "review_iteration": 0,
            "conversation_history": [],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        asyncio.run(orch._execute_agent_node(state))
        assert not any("Debug Hypotheses" in t for t in captured)
