"""Tests for Task #64: /debug and /errors CLI commands + StreamDisplay debug mode."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from lidco.cli.commands import CommandRegistry
from lidco.core.errors import ErrorHistory, ErrorRecord


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_session(debug_mode: bool = False):
    session = MagicMock()
    session.debug_mode = debug_mode
    session._error_history = ErrorHistory()
    return session


def _make_registry(session=None):
    reg = CommandRegistry()
    reg.set_session(session or _make_session())
    return reg


def _run(coro):
    return asyncio.run(coro)


def _make_record(n: int, tb: str | None = None) -> ErrorRecord:
    return ErrorRecord(
        id=str(n),
        timestamp=datetime.now(timezone.utc),
        tool_name=f"tool_{n}",
        agent_name="coder",
        error_type="tool_error",
        message=f"error message {n}",
        traceback_str=tb,
        file_hint=None,
    )


# ── /debug command ────────────────────────────────────────────────────────────


class TestDebugCommand:
    def test_enable_debug_mode(self):
        session = _make_session(debug_mode=False)
        reg = _make_registry(session)
        result = _run(reg.get("debug").handler(arg="on"))
        assert session.debug_mode is True
        assert "enabled" in result.lower()

    def test_disable_debug_mode(self):
        session = _make_session(debug_mode=True)
        reg = _make_registry(session)
        result = _run(reg.get("debug").handler(arg="off"))
        assert session.debug_mode is False
        assert "disabled" in result.lower()

    def test_true_enables(self):
        session = _make_session()
        reg = _make_registry(session)
        _run(reg.get("debug").handler(arg="true"))
        assert session.debug_mode is True

    def test_false_disables(self):
        session = _make_session(debug_mode=True)
        reg = _make_registry(session)
        _run(reg.get("debug").handler(arg="false"))
        assert session.debug_mode is False

    def test_no_arg_shows_state_enabled(self):
        session = _make_session(debug_mode=True)
        reg = _make_registry(session)
        result = _run(reg.get("debug").handler(arg=""))
        assert "enabled" in result.lower()

    def test_no_arg_shows_state_disabled(self):
        session = _make_session(debug_mode=False)
        reg = _make_registry(session)
        result = _run(reg.get("debug").handler(arg=""))
        assert "disabled" in result.lower()

    def test_invalid_arg_returns_usage(self):
        session = _make_session()
        reg = _make_registry(session)
        result = _run(reg.get("debug").handler(arg="maybe"))
        assert "usage" in result.lower() or "Unknown" in result

    def test_no_session_returns_message(self):
        reg = CommandRegistry()
        result = _run(reg.get("debug").handler(arg="on"))
        assert "not initialized" in result.lower()

    def test_unknown_arg_mentions_analyze(self):
        session = _make_session()
        reg = _make_registry(session)
        result = _run(reg.get("debug").handler(arg="blah"))
        assert "analyze" in result.lower() or "usage" in result.lower()


# ── /debug analyze subcommand ──────────────────────────────────────────────────


class TestDebugAnalyzeCommand:
    def _make_session_with_orchestrator(self, error_history=None):
        from unittest.mock import AsyncMock as _AM
        from lidco.agents.base import AgentResponse, TokenUsage

        session = _make_session()
        if error_history is not None:
            session._error_history = error_history
        mock_orch = MagicMock()
        mock_orch.handle = _AM(return_value=AgentResponse(
            content="Debugger analysis result",
            tool_calls_made=[],
            iterations=1,
            model_used="m",
            token_usage=TokenUsage(),
        ))
        session.orchestrator = mock_orch
        return session

    def test_analyze_no_errors_returns_message(self):
        session = self._make_session_with_orchestrator()  # empty history
        reg = _make_registry(session)
        result = _run(reg.get("debug").handler(arg="analyze"))
        assert "no errors" in result.lower()

    def test_analyze_calls_session_handle_with_debugger(self):
        history = ErrorHistory()
        history.append(_make_record(1, tb="Traceback:\n  File foo.py\nError"))
        session = self._make_session_with_orchestrator(error_history=history)
        reg = _make_registry(session)
        result = _run(reg.get("debug").handler(arg="analyze"))
        # Should have called orchestrator.handle
        session.orchestrator.handle.assert_called_once()
        call_kwargs = session.orchestrator.handle.call_args
        assert call_kwargs.kwargs.get("agent_name") == "debugger"
        # Response content should be returned
        assert "Debugger analysis result" in result

    def test_analyze_error_context_passed_in_message(self):
        history = ErrorHistory()
        history.append(_make_record(1, tb="Traceback:\n  File foo.py\nValueError: bang"))
        session = self._make_session_with_orchestrator(error_history=history)
        reg = _make_registry(session)
        _run(reg.get("debug").handler(arg="analyze"))

        call_args = session.orchestrator.handle.call_args
        message = call_args.args[0] if call_args.args else call_args.kwargs.get("user_message", "")
        assert "Recent Errors" in message or "error" in message.lower()

    def test_analyze_no_session_returns_message(self):
        reg = CommandRegistry()
        result = _run(reg.get("debug").handler(arg="analyze"))
        assert "not initialized" in result.lower()


# ── /errors command ───────────────────────────────────────────────────────────


class TestErrorsCommand:
    def test_no_errors_returns_message(self):
        session = _make_session()
        reg = _make_registry(session)
        result = _run(reg.get("errors").handler())
        assert "No errors" in result

    def test_shows_error_records(self):
        session = _make_session()
        session._error_history.append(_make_record(1))
        session._error_history.append(_make_record(2))
        reg = _make_registry(session)
        result = _run(reg.get("errors").handler())
        assert "tool_1" in result or "tool_2" in result
        assert "error message" in result

    def test_respects_n_argument(self):
        session = _make_session()
        for i in range(10):
            session._error_history.append(_make_record(i))
        reg = _make_registry(session)
        result = _run(reg.get("errors").handler(arg="3"))
        # Should show at most 3 entries — table title says "last 3"
        assert "3" in result

    def test_includes_traceback_when_available(self):
        session = _make_session()
        tb = 'Traceback (most recent call last):\n  File "src/foo.py", line 10\nValueError: bad'
        session._error_history.append(_make_record(1, tb=tb))
        reg = _make_registry(session)
        result = _run(reg.get("errors").handler())
        assert "traceback" in result.lower() or "ValueError" in result

    def test_invalid_n_returns_error(self):
        session = _make_session()
        reg = _make_registry(session)
        result = _run(reg.get("errors").handler(arg="abc"))
        assert "Invalid" in result or "invalid" in result.lower()

    def test_no_session_returns_message(self):
        reg = CommandRegistry()
        result = _run(reg.get("errors").handler())
        assert "not initialized" in result.lower()

    def test_large_n_capped_at_50(self):
        """Providing n=200 should not crash — capped at 50."""
        session = _make_session()
        for i in range(5):
            session._error_history.append(_make_record(i))
        reg = _make_registry(session)
        result = _run(reg.get("errors").handler(arg="200"))
        assert "error message" in result


# ── StreamDisplay debug mode ──────────────────────────────────────────────────


class TestStreamDisplayDebugMode:
    def _make_display(self):
        from rich.console import Console
        from lidco.cli.stream_display import StreamDisplay
        buf = StringIO()
        console = Console(file=buf, force_terminal=False, width=120, no_color=True)
        display = StreamDisplay.__new__(StreamDisplay)
        display._console = console
        display._has_content = False
        display._needs_newline = False
        display._debug_mode = False
        display._status_bar = MagicMock()
        display._live = MagicMock()
        return display, buf

    def test_set_debug_mode_true(self):
        from lidco.cli.stream_display import StreamDisplay
        display, _ = self._make_display()
        display.set_debug_mode(True)
        assert display._debug_mode is True

    def test_set_debug_mode_false(self):
        from lidco.cli.stream_display import StreamDisplay
        display, _ = self._make_display()
        display.set_debug_mode(True)
        display.set_debug_mode(False)
        assert display._debug_mode is False

    def test_debug_panel_rendered_on_failure_when_enabled(self):
        from lidco.tools.base import ToolResult
        display, buf = self._make_display()
        display._debug_mode = True

        result = ToolResult(
            output="",
            success=False,
            error="boom",
            traceback_str="Traceback:\n  File foo.py line 1\nRuntimeError: boom",
        )
        display._on_tool_end("bash", {}, result)
        output = buf.getvalue()
        assert "Tool Error" in output or "boom" in output

    def test_simple_error_line_when_debug_disabled(self):
        from lidco.tools.base import ToolResult
        display, buf = self._make_display()
        display._debug_mode = False

        result = ToolResult(
            output="",
            success=False,
            error="short error",
            traceback_str="Traceback:\n  File foo.py line 1\nRuntimeError",
        )
        display._on_tool_end("bash", {}, result)
        output = buf.getvalue()
        # Simple one-liner — no Panel title
        assert "Tool Error" not in output

    def test_no_traceback_shows_simple_error_even_in_debug_mode(self):
        from lidco.tools.base import ToolResult
        display, buf = self._make_display()
        display._debug_mode = True

        result = ToolResult(output="", success=False, error="plain error")
        display._on_tool_end("bash", {}, result)
        output = buf.getvalue()
        assert "plain error" in output
