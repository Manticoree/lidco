"""Tests for Task C: LLM error capture in BaseAgent.run()."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.core.errors import ErrorRecord
from lidco.llm.exceptions import LLMRetryExhausted


# ── Helpers ───────────────────────────────────────────────────────────────────


class ConcreteAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        return self._config.system_prompt


def _make_config(name: str = "coder") -> AgentConfig:
    return AgentConfig(
        name=name,
        description="test",
        system_prompt="You are helpful.",
        tools=[],
        max_iterations=1,
    )


def _make_agent(name: str = "coder") -> tuple[ConcreteAgent, MagicMock]:
    config = _make_config(name)
    llm = MagicMock()
    registry = MagicMock()
    registry.list_tools.return_value = []
    agent = ConcreteAgent(config=config, llm=llm, tool_registry=registry)
    return agent, llm


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestLLMErrorCapture:
    def test_llm_retry_exhausted_fires_callback(self):
        """When complete() raises LLMRetryExhausted, _error_callback is fired."""
        agent, llm = _make_agent()
        exc = LLMRetryExhausted("all retries failed", attempts=[("model-x", RuntimeError("500"))])
        llm.complete = AsyncMock(side_effect=exc)

        captured: list[ErrorRecord] = []
        agent.set_error_callback(lambda r: captured.append(r))

        with pytest.raises(LLMRetryExhausted):
            asyncio.run(agent.run("hello"))

        assert len(captured) == 1
        rec = captured[0]
        assert rec.error_type == "llm_error"
        assert rec.tool_name == "llm"
        assert rec.agent_name == "coder"
        assert "retries" in rec.message.lower() or rec.message  # some message

    def test_llm_retry_exhausted_record_has_correct_agent_name(self):
        agent, llm = _make_agent(name="debugger")
        exc = LLMRetryExhausted("fail")
        llm.complete = AsyncMock(side_effect=exc)

        captured: list[ErrorRecord] = []
        agent.set_error_callback(lambda r: captured.append(r))

        with pytest.raises(LLMRetryExhausted):
            asyncio.run(agent.run("analyze this"))

        assert captured[0].agent_name == "debugger"

    def test_exception_re_raised_after_callback(self):
        """The exception must propagate even after the callback fires."""
        agent, llm = _make_agent()
        exc = LLMRetryExhausted("gone")
        llm.complete = AsyncMock(side_effect=exc)
        agent.set_error_callback(lambda r: None)

        with pytest.raises(LLMRetryExhausted):
            asyncio.run(agent.run("x"))

    def test_no_callback_does_not_suppress_exception(self):
        """With no callback set, LLMRetryExhausted still propagates."""
        agent, llm = _make_agent()
        exc = LLMRetryExhausted("fail")
        llm.complete = AsyncMock(side_effect=exc)
        # No callback set

        with pytest.raises(LLMRetryExhausted):
            asyncio.run(agent.run("hello"))

    def test_other_exceptions_not_treated_as_llm_error(self):
        """A plain RuntimeError is not recorded as an llm_error."""
        agent, llm = _make_agent()
        llm.complete = AsyncMock(side_effect=RuntimeError("boom"))

        captured: list[ErrorRecord] = []
        agent.set_error_callback(lambda r: captured.append(r))

        with pytest.raises(RuntimeError):
            asyncio.run(agent.run("hello"))

        # No llm_error record should have been appended
        llm_errors = [r for r in captured if r.error_type == "llm_error"]
        assert llm_errors == []

    def test_llm_error_record_has_no_traceback(self):
        """LLM errors have traceback_str=None and file_hint=None."""
        agent, llm = _make_agent()
        llm.complete = AsyncMock(side_effect=LLMRetryExhausted("x"))

        captured: list[ErrorRecord] = []
        agent.set_error_callback(lambda r: captured.append(r))

        with pytest.raises(LLMRetryExhausted):
            asyncio.run(agent.run("go"))

        rec = captured[0]
        assert rec.traceback_str is None
        assert rec.file_hint is None
