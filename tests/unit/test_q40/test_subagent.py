"""Tests for Q40 — SubagentTool (Task 275)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.tools.subagent import SubagentTool
from lidco.tools.base import ToolPermission


def _make_session(agent_exists: bool = True, response_content: str = "result") -> MagicMock:
    session = MagicMock()
    # agent_registry.get returns agent or None
    if agent_exists:
        session.agent_registry.get.return_value = MagicMock()
        session.agent_registry.list_names.return_value = ["coder"]
    else:
        session.agent_registry.get.return_value = None
        session.agent_registry.list_names.return_value = []
    # orchestrator.handle returns an AgentResponse-like object
    resp = MagicMock()
    resp.content = response_content
    session.orchestrator.handle = AsyncMock(return_value=resp)
    session.get_full_context.return_value = "base context"
    return session


class TestSubagentToolMeta:
    def test_name(self):
        tool = SubagentTool(MagicMock())
        assert tool.name == "subagent"

    def test_permission_is_ask(self):
        tool = SubagentTool(MagicMock())
        assert tool.permission == ToolPermission.ASK

    def test_parameters_include_required_fields(self):
        tool = SubagentTool(MagicMock())
        params = {p.name: p for p in tool.parameters}
        assert "agent_name" in params
        assert "task" in params
        assert params["agent_name"].required is True
        assert params["task"].required is True

    def test_context_param_is_optional(self):
        tool = SubagentTool(MagicMock())
        params = {p.name: p for p in tool.parameters}
        assert "context" in params
        assert params["context"].required is False


class TestSubagentToolRun:
    def test_successful_delegation(self):
        session = _make_session(agent_exists=True, response_content="agent output")
        tool = SubagentTool(session)

        async def run():
            return await tool._run(agent_name="coder", task="write a function")

        result = asyncio.run(run())
        assert result.success is True
        assert result.output == "agent output"

    def test_unknown_agent_returns_error(self):
        session = _make_session(agent_exists=False)
        tool = SubagentTool(session)

        async def run():
            return await tool._run(agent_name="ghost", task="do something")

        result = asyncio.run(run())
        assert result.success is False
        assert "ghost" in result.error
        assert "not found" in result.error.lower()

    def test_max_depth_exceeded_returns_error(self):
        session = _make_session()
        tool = SubagentTool(session)
        tool._depth = SubagentTool._MAX_DEPTH

        async def run():
            return await tool._run(agent_name="coder", task="nested")

        result = asyncio.run(run())
        assert result.success is False
        assert "depth" in result.error.lower() or "recursion" in result.error.lower()

    def test_depth_increments_and_decrements(self):
        session = _make_session()
        tool = SubagentTool(session)
        depths: list[int] = []

        original_handle = session.orchestrator.handle

        async def record_depth(*a, **kw):
            depths.append(tool._depth)
            return await original_handle(*a, **kw)

        session.orchestrator.handle = record_depth

        async def run():
            assert tool._depth == 0
            await tool._run(agent_name="coder", task="x")
            assert tool._depth == 0  # restored after

        asyncio.run(run())
        assert depths == [1]

    def test_exception_returns_error_result(self):
        session = _make_session()
        session.orchestrator.handle = AsyncMock(side_effect=RuntimeError("boom"))
        tool = SubagentTool(session)

        async def run():
            return await tool._run(agent_name="coder", task="crash")

        result = asyncio.run(run())
        assert result.success is False
        assert "boom" in result.error

    def test_depth_restored_after_exception(self):
        session = _make_session()
        session.orchestrator.handle = AsyncMock(side_effect=RuntimeError("err"))
        tool = SubagentTool(session)

        async def run():
            await tool._run(agent_name="coder", task="crash")
            return tool._depth

        depth = asyncio.run(run())
        assert depth == 0

    def test_context_passed_to_orchestrator(self):
        session = _make_session()
        tool = SubagentTool(session)

        async def run():
            return await tool._run(
                agent_name="coder",
                task="write tests",
                context="extra context",
            )

        asyncio.run(run())
        call_kwargs = session.orchestrator.handle.call_args
        assert call_kwargs is not None
        # context should be passed
        ctx_arg = call_kwargs[1].get("context") or (call_kwargs[0][2] if len(call_kwargs[0]) > 2 else "")
        assert "extra context" in ctx_arg or "base context" in ctx_arg

    def test_no_agent_registry_still_works(self):
        """When session has no agent_registry, validation is skipped."""
        session = MagicMock(spec=[])  # no attributes
        session.orchestrator = MagicMock()
        resp = MagicMock()
        resp.content = "ok"
        session.orchestrator.handle = AsyncMock(return_value=resp)
        tool = SubagentTool(session)

        async def run():
            return await tool._run(agent_name="any", task="do it")

        result = asyncio.run(run())
        assert result.success is True

    def test_string_response_fallback(self):
        """When response has no .content, str() is used."""
        session = _make_session()
        session.orchestrator.handle = AsyncMock(return_value="plain string")
        tool = SubagentTool(session)

        async def run():
            return await tool._run(agent_name="coder", task="go")

        result = asyncio.run(run())
        assert result.success is True
        assert result.output == "plain string"
