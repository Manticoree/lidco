"""Tests for SubagentTool extensions — Task 394 (wait + context_passthrough)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.subagent import SubagentTool
from lidco.tools.base import ToolResult


def _make_session(response_content: str = "agent output") -> MagicMock:
    session = MagicMock()
    session.get_full_context.return_value = ""
    session.agent_registry = None  # skip validation
    resp = MagicMock(content=response_content)
    session.orchestrator.handle = AsyncMock(return_value=resp)
    bg_mgr = MagicMock()
    bg_mgr.submit.return_value = "abc12345"
    session.background_tasks = bg_mgr
    return session


class TestSubagentToolParameters:
    def test_has_wait_parameter(self):
        tool = SubagentTool(MagicMock())
        param_names = [p.name for p in tool.parameters]
        assert "wait" in param_names

    def test_has_context_passthrough_parameter(self):
        tool = SubagentTool(MagicMock())
        param_names = [p.name for p in tool.parameters]
        assert "context_passthrough" in param_names

    def test_wait_is_not_required(self):
        tool = SubagentTool(MagicMock())
        wait_param = next(p for p in tool.parameters if p.name == "wait")
        assert wait_param.required is False

    def test_context_passthrough_is_not_required(self):
        tool = SubagentTool(MagicMock())
        cp_param = next(p for p in tool.parameters if p.name == "context_passthrough")
        assert cp_param.required is False


class TestSubagentToolWaitTrue:
    @pytest.mark.asyncio
    async def test_wait_true_returns_content(self):
        session = _make_session("sync result")
        tool = SubagentTool(session)
        result = await tool._run(agent_name="coder", task="do it", wait=True)
        assert result.success is True
        assert result.output == "sync result"

    @pytest.mark.asyncio
    async def test_wait_true_is_default(self):
        session = _make_session("default sync")
        tool = SubagentTool(session)
        result = await tool._run(agent_name="coder", task="task")
        assert result.success is True
        assert result.output == "default sync"


class TestSubagentToolWaitFalse:
    @pytest.mark.asyncio
    async def test_wait_false_submits_to_background(self):
        session = _make_session()
        tool = SubagentTool(session)
        result = await tool._run(agent_name="coder", task="do it", wait=False)
        assert result.success is True
        assert "abc12345" in result.output
        session.background_tasks.submit.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_false_returns_task_id_in_metadata(self):
        session = _make_session()
        tool = SubagentTool(session)
        result = await tool._run(agent_name="coder", task="task", wait=False)
        assert result.metadata is not None
        assert result.metadata.get("task_id") == "abc12345"

    @pytest.mark.asyncio
    async def test_wait_false_without_background_manager_fails(self):
        session = _make_session()
        session.background_tasks = None
        tool = SubagentTool(session)
        result = await tool._run(agent_name="coder", task="task", wait=False)
        assert not result.success
        assert "BackgroundTaskManager" in result.error


class TestSubagentToolContextPassthrough:
    @pytest.mark.asyncio
    async def test_context_passthrough_prepended(self):
        session = _make_session("ok")
        session.get_full_context.return_value = ""
        tool = SubagentTool(session)
        await tool._run(agent_name="coder", task="task", context_passthrough="IMPORTANT: use Python 3.12")
        call_kwargs = session.orchestrator.handle.call_args
        # context is passed as keyword arg
        ctx_arg = call_kwargs.kwargs.get("context") or (call_kwargs.args[2] if len(call_kwargs.args) > 2 else "")
        assert "IMPORTANT: use Python 3.12" in ctx_arg

    @pytest.mark.asyncio
    async def test_context_passthrough_combined_with_existing_context(self):
        session = _make_session("ok")
        session.get_full_context.return_value = "base context"
        tool = SubagentTool(session)
        await tool._run(agent_name="coder", task="task", context="extra", context_passthrough="passthrough")
        call_kwargs = session.orchestrator.handle.call_args
        ctx_arg = call_kwargs.kwargs.get("context") or ""
        assert "passthrough" in ctx_arg
        assert "extra" in ctx_arg


class TestSubagentMaxDepth:
    @pytest.mark.asyncio
    async def test_max_depth_blocked(self):
        session = _make_session()
        tool = SubagentTool(session)
        tool._depth = tool._MAX_DEPTH
        result = await tool._run(agent_name="coder", task="task")
        assert not result.success
        assert "recursion" in result.error.lower() or "depth" in result.error.lower()
