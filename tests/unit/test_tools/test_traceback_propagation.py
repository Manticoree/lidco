"""Tests for Task #61: stack trace propagation through ToolResult and BaseAgent."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from lidco.tools.base import ToolResult, BaseTool
from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry


# ── ToolResult ────────────────────────────────────────────────────────────────


class TestToolResultBackwardCompat:
    """ToolResult still works without traceback_str."""

    def test_success_no_traceback(self):
        r = ToolResult(output="ok")
        assert r.success is True
        assert r.traceback_str is None

    def test_error_no_traceback(self):
        r = ToolResult(output="", success=False, error="oops")
        assert r.traceback_str is None

    def test_traceback_str_stored(self):
        r = ToolResult(output="", success=False, error="bad", traceback_str="Traceback (most recent call last):\n  ...")
        assert r.traceback_str is not None
        assert "Traceback" in r.traceback_str

    def test_frozen_dataclass(self):
        r = ToolResult(output="x")
        with pytest.raises((AttributeError, TypeError)):
            r.output = "y"  # type: ignore[misc]


class TestBaseToolTracebackCapture:
    """BaseTool.execute() must capture full traceback on exception."""

    def test_traceback_captured_on_exception(self):
        import asyncio

        class BoomTool(BaseTool):
            @property
            def name(self) -> str:
                return "boom"

            @property
            def description(self) -> str:
                return "always explodes"

            @property
            def parameters(self):
                return []

            async def _run(self, **kwargs):
                raise ValueError("intentional boom")

        tool = BoomTool()
        result = asyncio.run(tool.execute())

        assert result.success is False
        assert result.error == "intentional boom"
        assert result.traceback_str is not None
        assert "ValueError" in result.traceback_str
        assert "intentional boom" in result.traceback_str

    def test_traceback_contains_file_info(self):
        import asyncio

        class LineTool(BaseTool):
            @property
            def name(self) -> str:
                return "line"

            @property
            def description(self) -> str:
                return "raises with file info"

            @property
            def parameters(self):
                return []

            async def _run(self, **kwargs):
                raise RuntimeError("line error")

        tool = LineTool()
        result = asyncio.run(tool.execute())
        assert "File" in result.traceback_str or "line" in result.traceback_str.lower()

    def test_success_has_no_traceback(self):
        import asyncio

        class OkTool(BaseTool):
            @property
            def name(self) -> str:
                return "ok"

            @property
            def description(self) -> str:
                return "succeeds"

            @property
            def parameters(self):
                return []

            async def _run(self, **kwargs):
                return ToolResult(output="good")

        tool = OkTool()
        result = asyncio.run(tool.execute())
        assert result.success is True
        assert result.traceback_str is None


# ── BaseAgent._format_tool_result ─────────────────────────────────────────────


class _DummyAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        return "dummy"


def _make_agent() -> _DummyAgent:
    config = AgentConfig(name="test", description="t", system_prompt="s")
    llm = MagicMock(spec=BaseLLMProvider)
    registry = ToolRegistry()
    return _DummyAgent(config=config, llm=llm, tool_registry=registry)


class TestFormatToolResult:
    def test_success_returns_output(self):
        agent = _make_agent()
        r = ToolResult(output="hello world")
        assert agent._format_tool_result(r) == "hello world"

    def test_error_without_traceback(self):
        agent = _make_agent()
        r = ToolResult(output="", success=False, error="file not found")
        result = agent._format_tool_result(r)
        assert result == "Error: file not found"

    def test_error_with_traceback(self):
        agent = _make_agent()
        tb = "Traceback (most recent call last):\n  File x.py, line 5\nKeyError: 'key'"
        r = ToolResult(output="", success=False, error="KeyError", traceback_str=tb)
        result = agent._format_tool_result(r)
        assert "Error: KeyError" in result
        assert "Traceback:" in result
        assert "KeyError: 'key'" in result

    def test_traceback_capped_at_3000(self):
        agent = _make_agent()
        long_tb = "X" * 5000
        r = ToolResult(output="", success=False, error="e", traceback_str=long_tb)
        result = agent._format_tool_result(r)
        assert "[traceback truncated]" in result
        # The traceback portion should be capped
        assert len(result) < 5000 + 200  # some overhead for prefix text

    def test_traceback_not_truncated_when_short(self):
        agent = _make_agent()
        short_tb = "Traceback:\n  short"
        r = ToolResult(output="", success=False, error="e", traceback_str=short_tb)
        result = agent._format_tool_result(r)
        assert "[traceback truncated]" not in result
        assert "short" in result

    def test_custom_cap(self):
        agent = _make_agent()
        tb = "A" * 200
        r = ToolResult(output="", success=False, error="e", traceback_str=tb)
        result = agent._format_tool_result(r, traceback_cap=50)
        assert "[traceback truncated]" in result
