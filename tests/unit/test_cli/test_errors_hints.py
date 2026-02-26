"""Tests for error taxonomy hints in the /errors CLI command."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


# ── _get_error_hint ───────────────────────────────────────────────────────────
# We test the helper indirectly by invoking errors_handler through the
# CommandRegistry, which is the integration point.


def _make_session(records):
    """Build a minimal mock session that holds the given ErrorRecords."""
    from lidco.core.errors import ErrorHistory
    hist = ErrorHistory()
    for r in records:
        hist._records = hist._records + [r]

    session = MagicMock()
    session._error_history = hist
    return session


def _make_record(message: str):
    from lidco.core.errors import ErrorRecord
    return ErrorRecord(
        id="x",
        timestamp=datetime.now(timezone.utc),
        tool_name="bash",
        agent_name="coder",
        error_type="tool_error",
        message=message,
        traceback_str=None,
        file_hint=None,
    )


# ── taxonomy hint mapping tests ───────────────────────────────────────────────


class TestGetErrorHint:
    """Test the taxonomy hint lookup used inside errors_handler.

    We instantiate the CommandRegistry to get access to the inner helper.
    The helper is defined at closure scope inside _register_builtins so we
    test it via the full handler integration.
    """

    def _run_errors(self, message: str) -> str:
        """Run /errors with a single record and return the rendered table string."""
        from lidco.cli.commands import CommandRegistry

        reg = CommandRegistry()
        reg._session = _make_session([_make_record(message)])

        cmd = reg.get("errors")
        return asyncio.run(cmd.handler("1"))

    def test_none_type_attribute_error_hint(self):
        result = self._run_errors("'NoneType' object has no attribute 'run'")
        assert "Add None guard" in result

    def test_takes_positional_argument_hint(self):
        result = self._run_errors("takes 2 positional arguments but 3 were given")
        # Either "Check call signature" or "Check call signature"
        assert "Check call signature" in result or "call signature" in result.lower()

    def test_key_error_hint(self):
        result = self._run_errors("KeyError: 'missing_key'")
        assert "Use .get()" in result or ".get()" in result

    def test_file_not_found_hint(self):
        result = self._run_errors("FileNotFoundError: No such file or directory")
        assert "path" in result.lower() or "cwd" in result.lower()

    def test_module_not_found_hint(self):
        result = self._run_errors("ModuleNotFoundError: No module named 'foo'")
        assert "dep" in result.lower() or "installed" in result.lower()

    def test_unknown_error_no_hint(self):
        result = self._run_errors("some completely unknown error xyz123")
        # No hint should appear — just verify it doesn't crash
        # The table still renders
        assert "bash" in result

    def test_no_errors_returns_message(self):
        from lidco.cli.commands import CommandRegistry
        reg = CommandRegistry()
        from lidco.core.errors import ErrorHistory
        session = MagicMock()
        session._error_history = ErrorHistory()
        reg._session = session

        cmd = reg.get("errors")
        result = asyncio.run(cmd.handler("5"))
        assert "No errors" in result


# ── occurrence count in table ─────────────────────────────────────────────────


class TestOccurrenceCountInTable:
    def test_repeat_count_shown_for_deduplicated_errors(self):
        from lidco.core.errors import ErrorRecord, ErrorHistory
        from lidco.cli.commands import CommandRegistry

        h = ErrorHistory()
        # Manually add a record with occurrence_count > 1
        rec = ErrorRecord(
            id="z",
            timestamp=datetime.now(timezone.utc),
            tool_name="bash",
            agent_name="coder",
            error_type="tool_error",
            message="repeated error",
            traceback_str=None,
            file_hint=None,
            occurrence_count=5,
        )
        h._records = [rec]

        session = MagicMock()
        session._error_history = h
        reg = CommandRegistry()
        reg._session = session

        cmd = reg.get("errors")
        result = asyncio.run(cmd.handler("5"))
        assert "5" in result  # repeat count shown in × column
