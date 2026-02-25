"""Tests for Task #62: ErrorRecord, ErrorHistory, extract_file_hint, callback wiring."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.core.errors import ErrorHistory, ErrorRecord, extract_file_hint
from lidco.tools.base import ToolResult


# ── extract_file_hint ─────────────────────────────────────────────────────────


class TestExtractFileHint:
    def test_finds_py_file(self):
        tb = 'Traceback (most recent call last):\n  File "/home/user/src/foo.py", line 5, in bar\n    raise ValueError'
        assert extract_file_hint(tb) == "/home/user/src/foo.py"

    def test_returns_none_for_none(self):
        assert extract_file_hint(None) is None

    def test_returns_none_for_no_file(self):
        assert extract_file_hint("some plain error text") is None

    def test_returns_first_match(self):
        tb = 'File "a.py", line 1\nFile "b.py", line 2'
        assert extract_file_hint(tb) == "a.py"

    def test_ignores_non_py_files(self):
        tb = 'File "config.yaml", line 1'
        assert extract_file_hint(tb) is None


# ── ErrorRecord ───────────────────────────────────────────────────────────────


class TestErrorRecord:
    def test_frozen_dataclass(self):
        rec = ErrorRecord(
            id="abc",
            timestamp=datetime.now(timezone.utc),
            tool_name="file_read",
            agent_name="coder",
            error_type="tool_error",
            message="file not found",
            traceback_str=None,
            file_hint=None,
        )
        with pytest.raises((AttributeError, TypeError)):
            rec.id = "new"  # type: ignore[misc]

    def test_fields_stored(self):
        ts = datetime.now(timezone.utc)
        rec = ErrorRecord(
            id="x1",
            timestamp=ts,
            tool_name="bash",
            agent_name="debugger",
            error_type="exception",
            message="oops",
            traceback_str="Traceback...",
            file_hint="foo.py",
        )
        assert rec.tool_name == "bash"
        assert rec.agent_name == "debugger"
        assert rec.error_type == "exception"
        assert rec.file_hint == "foo.py"


# ── ErrorHistory ──────────────────────────────────────────────────────────────


def _make_record(n: int) -> ErrorRecord:
    return ErrorRecord(
        id=str(n),
        timestamp=datetime.now(timezone.utc),
        tool_name=f"tool_{n}",
        agent_name="coder",
        error_type="tool_error",
        message=f"error {n}",
        traceback_str=None,
        file_hint=None,
    )


class TestErrorHistory:
    def test_empty_on_init(self):
        h = ErrorHistory()
        assert len(h) == 0

    def test_append_and_len(self):
        h = ErrorHistory()
        h.append(_make_record(1))
        assert len(h) == 1

    def test_get_recent_returns_correct_count(self):
        h = ErrorHistory()
        for i in range(10):
            h.append(_make_record(i))
        recent = h.get_recent(3)
        assert len(recent) == 3
        # Most recent entries
        assert recent[-1].message == "error 9"

    def test_ring_buffer_caps_at_max_size(self):
        h = ErrorHistory(max_size=5)
        for i in range(10):
            h.append(_make_record(i))
        assert len(h) == 5
        # Only the last 5 entries remain
        recent = h.get_recent(10)
        messages = [r.message for r in recent]
        assert "error 5" in messages
        assert "error 0" not in messages

    def test_clear_removes_all(self):
        h = ErrorHistory()
        h.append(_make_record(1))
        h.append(_make_record(2))
        h.clear()
        assert len(h) == 0

    def test_immutable_list_swaps(self):
        """append() must not mutate in place (functional replacement)."""
        h = ErrorHistory()
        h.append(_make_record(1))
        original = h._records
        h.append(_make_record(2))
        assert h._records is not original

    def test_get_recent_empty(self):
        h = ErrorHistory()
        assert h.get_recent(5) == []


# ── to_context_str ────────────────────────────────────────────────────────────


class TestToContextStr:
    def test_empty_history_returns_empty_string(self):
        h = ErrorHistory()
        assert h.to_context_str() == ""

    def test_contains_section_header(self):
        h = ErrorHistory()
        h.append(_make_record(1))
        ctx = h.to_context_str()
        assert "## Recent Errors" in ctx

    def test_contains_tool_name_and_message(self):
        h = ErrorHistory()
        rec = ErrorRecord(
            id="r1",
            timestamp=datetime.now(timezone.utc),
            tool_name="file_edit",
            agent_name="coder",
            error_type="tool_error",
            message="old_string not found",
            traceback_str=None,
            file_hint=None,
        )
        h.append(rec)
        ctx = h.to_context_str()
        assert "file_edit" in ctx
        assert "old_string not found" in ctx

    def test_truncates_message_to_120_chars(self):
        h = ErrorHistory()
        long_msg = "X" * 200
        rec = ErrorRecord(
            id="r2",
            timestamp=datetime.now(timezone.utc),
            tool_name="t",
            agent_name="a",
            error_type="tool_error",
            message=long_msg,
            traceback_str=None,
            file_hint=None,
        )
        h.append(rec)
        ctx = h.to_context_str()
        # The rendered message should be no longer than 120 Xs
        assert "X" * 121 not in ctx

    def test_includes_file_hint(self):
        h = ErrorHistory()
        rec = ErrorRecord(
            id="r3",
            timestamp=datetime.now(timezone.utc),
            tool_name="t",
            agent_name="a",
            error_type="exception",
            message="err",
            traceback_str='File "src/foo.py", line 10',
            file_hint="src/foo.py",
        )
        h.append(rec)
        ctx = h.to_context_str()
        assert "src/foo.py" in ctx

    def test_includes_traceback_last_lines(self):
        h = ErrorHistory()
        tb = "\n".join(f"line {i}" for i in range(20))
        rec = ErrorRecord(
            id="r4",
            timestamp=datetime.now(timezone.utc),
            tool_name="t",
            agent_name="a",
            error_type="exception",
            message="err",
            traceback_str=tb,
            file_hint=None,
        )
        h.append(rec)
        ctx = h.to_context_str()
        # Should include last line
        assert "line 19" in ctx
        # Should NOT include very early lines (only last 5)
        assert "line 0\n" not in ctx

    def test_respects_n_limit(self):
        h = ErrorHistory()
        for i in range(10):
            h.append(_make_record(i))
        ctx = h.to_context_str(n=2)
        # Only 2 error entries — count bullet-point lines (start with "- **")
        bullet_count = sum(1 for line in ctx.splitlines() if line.startswith("- **"))
        assert bullet_count == 2


# ── BaseAgent error callback wiring ──────────────────────────────────────────


class _BoomTool:
    """Fake tool that always fails."""
    name = "boom"

    async def execute(self, **kwargs):
        return ToolResult(output="", success=False, error="boom error", traceback_str='File "boom.py", line 1\nRuntimeError')

    def set_progress_callback(self, cb):
        pass


class _OkTool:
    name = "ok_tool"

    async def execute(self, **kwargs):
        return ToolResult(output="fine")

    def set_progress_callback(self, cb):
        pass


def _make_agent_with_registry():
    from lidco.agents.base import AgentConfig, BaseAgent
    from lidco.llm.base import BaseLLMProvider
    from lidco.tools.registry import ToolRegistry

    class _Agent(BaseAgent):
        def get_system_prompt(self) -> str:
            return "s"

    config = AgentConfig(name="coder", description="d", system_prompt="s")
    llm = MagicMock(spec=BaseLLMProvider)
    registry = MagicMock(spec=ToolRegistry)
    agent = _Agent(config=config, llm=llm, tool_registry=registry)
    return agent, registry


class TestBaseAgentErrorCallback:
    def test_callback_fired_on_tool_failure(self):
        agent, registry = _make_agent_with_registry()
        boom = _BoomTool()
        registry.get.return_value = boom

        fired: list = []
        agent.set_error_callback(fired.append)

        asyncio.run(agent._execute_tool("boom", {}))
        assert len(fired) == 1
        record = fired[0]
        assert record.tool_name == "boom"
        assert record.error_type == "exception"
        assert record.message == "boom error"
        assert record.file_hint == "boom.py"

    def test_callback_not_fired_on_success(self):
        agent, registry = _make_agent_with_registry()
        ok = _OkTool()
        registry.get.return_value = ok

        fired: list = []
        agent.set_error_callback(fired.append)

        asyncio.run(agent._execute_tool("ok_tool", {}))
        assert fired == []

    def test_no_callback_set_does_not_raise(self):
        agent, registry = _make_agent_with_registry()
        boom = _BoomTool()
        registry.get.return_value = boom

        # No callback set — must not raise
        result = asyncio.run(agent._execute_tool("boom", {}))
        assert not result.success

    def test_record_has_uuid_id(self):
        import re as _re
        agent, registry = _make_agent_with_registry()
        registry.get.return_value = _BoomTool()

        fired: list = []
        agent.set_error_callback(fired.append)
        asyncio.run(agent._execute_tool("boom", {}))

        assert len(fired[0].id) == 32  # uuid4.hex is 32 hex chars
        assert _re.match(r"^[0-9a-f]{32}$", fired[0].id)

    def test_record_timestamp_is_utc(self):
        from datetime import timezone as _tz
        agent, registry = _make_agent_with_registry()
        registry.get.return_value = _BoomTool()

        fired: list = []
        agent.set_error_callback(fired.append)
        asyncio.run(agent._execute_tool("boom", {}))

        assert fired[0].timestamp.tzinfo is not None
