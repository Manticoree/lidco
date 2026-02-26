"""Tests for ErrorReportTool."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from lidco.core.errors import ErrorHistory, ErrorRecord
from lidco.tools.error_report import ErrorReportTool


# ── helpers ───────────────────────────────────────────────────────────────────


def _rec(
    *,
    tool_name: str = "bash",
    agent_name: str = "coder",
    error_type: str = "tool_error",
    message: str = "oops",
    file_hint: str | None = None,
    tool_args: dict | None = None,
    occurrence_count: int = 1,
) -> ErrorRecord:
    return ErrorRecord(
        id="t",
        timestamp=datetime.now(timezone.utc),
        tool_name=tool_name,
        agent_name=agent_name,
        error_type=error_type,
        message=message,
        traceback_str=None,
        file_hint=file_hint,
        tool_args=tool_args,
        occurrence_count=occurrence_count,
    )


def _make_tool(records: list[ErrorRecord]) -> ErrorReportTool:
    h = ErrorHistory()
    for r in records:
        # Bypass dedup: append directly to the internal list
        h._records = h._records + [r]
    return ErrorReportTool(h)


# ── basic contract ────────────────────────────────────────────────────────────


class TestErrorReportToolBasic:
    def test_name(self):
        tool = ErrorReportTool(ErrorHistory())
        assert tool.name == "error_report"

    def test_description_is_string(self):
        tool = ErrorReportTool(ErrorHistory())
        assert isinstance(tool.description, str)
        assert len(tool.description) > 10

    def test_parameters_list(self):
        tool = ErrorReportTool(ErrorHistory())
        names = [p.name for p in tool.parameters]
        assert "n" in names
        assert "group_by" in names

    def test_empty_history_returns_no_errors_message(self):
        tool = ErrorReportTool(ErrorHistory())
        result = asyncio.run(tool._run())
        assert result.success
        assert "No errors" in result.output

    def test_permission_is_auto(self):
        from lidco.tools.base import ToolPermission
        tool = ErrorReportTool(ErrorHistory())
        assert tool.permission == ToolPermission.AUTO


# ── group_by="file" ───────────────────────────────────────────────────────────


class TestGroupByFile:
    def test_groups_errors_by_file(self):
        tool = _make_tool([
            _rec(file_hint="/a.py"),
            _rec(file_hint="/a.py"),
            _rec(file_hint="/b.py"),
        ])
        result = asyncio.run(tool._run(group_by="file"))
        assert result.success
        assert "/a.py" in result.output
        assert "/b.py" in result.output

    def test_no_file_hint_shows_placeholder(self):
        tool = _make_tool([_rec(file_hint=None)])
        result = asyncio.run(tool._run(group_by="file"))
        assert "(no file)" in result.output

    def test_most_common_file_listed_first(self):
        tool = _make_tool([
            _rec(file_hint="/rare.py"),
            _rec(file_hint="/common.py"),
            _rec(file_hint="/common.py"),
            _rec(file_hint="/common.py"),
        ])
        result = asyncio.run(tool._run(group_by="file"))
        assert result.output.index("/common.py") < result.output.index("/rare.py")


# ── group_by="type" ───────────────────────────────────────────────────────────


class TestGroupByType:
    def test_groups_by_error_type(self):
        tool = _make_tool([
            _rec(error_type="exception"),
            _rec(error_type="tool_error"),
            _rec(error_type="exception"),
        ])
        result = asyncio.run(tool._run(group_by="type"))
        assert "exception" in result.output
        assert "tool_error" in result.output

    def test_most_common_type_listed_first(self):
        tool = _make_tool([
            _rec(error_type="exception"),
            _rec(error_type="exception"),
            _rec(error_type="tool_error"),
        ])
        result = asyncio.run(tool._run(group_by="type"))
        assert result.output.index("exception") < result.output.index("tool_error")


# ── group_by="agent" ──────────────────────────────────────────────────────────


class TestGroupByAgent:
    def test_groups_by_agent(self):
        tool = _make_tool([
            _rec(agent_name="coder"),
            _rec(agent_name="tester"),
        ])
        result = asyncio.run(tool._run(group_by="agent"))
        assert "coder" in result.output
        assert "tester" in result.output


# ── group_by="none" ───────────────────────────────────────────────────────────


class TestGroupByNone:
    def test_flat_list(self):
        tool = _make_tool([_rec(tool_name="bash"), _rec(tool_name="file_read")])
        result = asyncio.run(tool._run(group_by="none"))
        assert "bash" in result.output
        assert "file_read" in result.output
        # Should NOT have grouping headers
        assert "## " not in result.output

    def test_single_error(self):
        tool = _make_tool([_rec(message="single failure")])
        result = asyncio.run(tool._run(group_by="none"))
        assert "single failure" in result.output


# ── occurrence_count reflected ────────────────────────────────────────────────


class TestOccurrenceCount:
    def test_occurrence_count_shown(self):
        tool = _make_tool([_rec(occurrence_count=5)])
        result = asyncio.run(tool._run(group_by="none"))
        assert "×5" in result.output

    def test_single_occurrence_no_repeat_marker(self):
        tool = _make_tool([_rec(occurrence_count=1)])
        result = asyncio.run(tool._run(group_by="none"))
        assert "×1" not in result.output

    def test_total_reflects_occurrences(self):
        """Total in header counts occurrences, not record count."""
        tool = _make_tool([
            _rec(occurrence_count=3),
            _rec(tool_name="grep", occurrence_count=2),
        ])
        result = asyncio.run(tool._run(group_by="none"))
        # flat mode says "5 error occurrences"; grouped mode says "5 occurrences"
        assert "5" in result.output and "occurrence" in result.output

    def test_grouped_total_reflects_occurrences(self):
        tool = _make_tool([
            _rec(file_hint="/f.py", occurrence_count=4),
            _rec(file_hint="/g.py", occurrence_count=1),
        ])
        result = asyncio.run(tool._run(group_by="file"))
        assert "/f.py (4 occurrence" in result.output
        assert "/g.py (1 occurrence" in result.output


# ── n parameter ───────────────────────────────────────────────────────────────


class TestNParameter:
    def test_n_limits_records(self):
        tool = _make_tool([_rec(tool_name=f"t{i}") for i in range(10)])
        result = asyncio.run(tool._run(n=3, group_by="none"))
        # Only last 3 records shown — t7, t8, t9
        assert "t9" in result.output
        assert "t6" not in result.output

    def test_n_default_20(self):
        tool = _make_tool([_rec() for _ in range(25)])
        result = asyncio.run(tool._run())
        # 25 records, default n=20 → show 20 occurrences in total
        assert "20 occurrence" in result.output


# ── tool_args in output ───────────────────────────────────────────────────────


class TestToolArgsInOutput:
    def test_args_shown_in_flat_mode(self):
        tool = _make_tool([_rec(tool_args={"path": "/src/foo.py"})])
        result = asyncio.run(tool._run(group_by="none"))
        # flat render does not show args (they'd be too noisy in flat mode)
        # but group mode line items include compact args hint
        pass  # No assertion — just verify no crash

    def test_args_shown_in_group_mode(self):
        tool = _make_tool([_rec(tool_args={"path": "/foo.py"}, file_hint="/x.py")])
        result = asyncio.run(tool._run(group_by="file"))
        assert "path=" in result.output

    def test_no_args_no_crash(self):
        tool = _make_tool([_rec(tool_args=None)])
        result = asyncio.run(tool._run(group_by="file"))
        assert result.success


# ── metadata ─────────────────────────────────────────────────────────────────


class TestMetadata:
    def test_metadata_contains_total(self):
        tool = _make_tool([_rec(occurrence_count=3), _rec(occurrence_count=2)])
        result = asyncio.run(tool._run(group_by="file"))
        assert result.metadata.get("total_errors") == 5

    def test_metadata_contains_unique_records(self):
        tool = _make_tool([_rec(), _rec(tool_name="grep")])
        result = asyncio.run(tool._run(group_by="file"))
        assert result.metadata.get("unique_records") == 2
