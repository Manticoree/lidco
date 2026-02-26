"""Tests for Task A+B: ErrorHistory.get_file_snippets and to_context_str(extended=True)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lidco.core.errors import (
    ErrorHistory,
    ErrorRecord,
    _extract_file_lines,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_record(
    file_hint: str | None,
    traceback_str: str | None,
    *,
    tool_name: str = "file_read",
    agent_name: str = "coder",
    error_type: str = "tool_error",
    message: str = "something broke",
) -> ErrorRecord:
    return ErrorRecord(
        id="abc",
        timestamp=datetime.now(timezone.utc),
        tool_name=tool_name,
        agent_name=agent_name,
        error_type=error_type,
        message=message,
        traceback_str=traceback_str,
        file_hint=file_hint,
    )


# ── _extract_file_lines ───────────────────────────────────────────────────────


class TestExtractFileLines:
    def test_basic_extraction(self, tmp_path: Path):
        src = tmp_path / "example.py"
        lines = [f"line {i}\n" for i in range(1, 51)]
        src.write_text("".join(lines))

        result = _extract_file_lines(str(src), 25, lines_around=3)
        assert result is not None
        # Lines 22–28 should be present
        assert "22" in result
        assert "28" in result
        # Line 25 is the target — marked with >>>
        assert ">>>" in result

    def test_marker_on_target_line(self, tmp_path: Path):
        src = tmp_path / "mark.py"
        src.write_text("a\nb\nc\nd\ne\n")
        result = _extract_file_lines(str(src), 3, lines_around=1)
        assert result is not None
        lines = result.splitlines()
        # Line 3 ('c') should have >>> marker
        target_lines = [l for l in lines if ">>>" in l]
        assert len(target_lines) == 1
        assert "c" in target_lines[0]

    def test_clamps_to_file_start(self, tmp_path: Path):
        src = tmp_path / "short.py"
        src.write_text("x\ny\nz\n")
        result = _extract_file_lines(str(src), 1, lines_around=20)
        assert result is not None
        # Should not raise; shows all 3 lines
        assert "x" in result

    def test_clamps_to_file_end(self, tmp_path: Path):
        src = tmp_path / "short.py"
        src.write_text("a\nb\nc\n")
        result = _extract_file_lines(str(src), 3, lines_around=20)
        assert result is not None
        assert "a" in result

    def test_missing_file_returns_none(self):
        result = _extract_file_lines("/nonexistent/path/file.py", 10)
        assert result is None

    def test_line_numbers_in_output(self, tmp_path: Path):
        src = tmp_path / "nums.py"
        src.write_text("\n".join(f"l{i}" for i in range(1, 11)) + "\n")
        result = _extract_file_lines(str(src), 5, lines_around=2)
        assert result is not None
        # Line 3–7 should appear
        for n in (3, 4, 5, 6, 7):
            assert str(n) in result


# ── ErrorHistory.get_file_snippets ────────────────────────────────────────────


class TestGetFileSnippets:
    def test_empty_history_returns_empty(self):
        h = ErrorHistory()
        assert h.get_file_snippets() == ""

    def test_record_without_file_hint_skipped(self):
        h = ErrorHistory()
        h.append(_make_record(file_hint=None, traceback_str="Traceback:\n  line 1"))
        assert h.get_file_snippets() == ""

    def test_record_without_traceback_skipped(self):
        h = ErrorHistory()
        h.append(_make_record(file_hint="/some/file.py", traceback_str=None))
        assert h.get_file_snippets() == ""

    def test_record_without_line_no_in_traceback_skipped(self):
        h = ErrorHistory()
        tb = 'File "/some/file.py", no line here'
        h.append(_make_record(file_hint="/some/file.py", traceback_str=tb))
        assert h.get_file_snippets() == ""

    def test_missing_file_skipped(self):
        """A record with valid hint+traceback but unreadable file is silently skipped."""
        h = ErrorHistory()
        tb = 'File "/no/such/file.py", line 5\nAttributeError: boom'
        h.append(_make_record(file_hint="/no/such/file.py", traceback_str=tb))
        assert h.get_file_snippets() == ""

    def test_real_file_included(self, tmp_path: Path):
        src = tmp_path / "boom.py"
        src.write_text("\n".join(f"line_{i}" for i in range(1, 30)) + "\n")

        tb = f'File "{src}", line 15\nValueError: bang'
        h = ErrorHistory()
        h.append(_make_record(file_hint=str(src), traceback_str=tb))

        result = h.get_file_snippets()
        assert "## Failure-Site Snippets" in result
        assert str(src) in result
        assert ":15" in result
        assert "```python" in result
        # Should include code around line 15
        assert "line_15" in result

    def test_markdown_format(self, tmp_path: Path):
        src = tmp_path / "fmt.py"
        src.write_text("\n".join(f"x{i}" for i in range(1, 20)) + "\n")
        tb = f'File "{src}", line 5\nRuntimeError'
        h = ErrorHistory()
        h.append(_make_record(file_hint=str(src), traceback_str=tb))

        result = h.get_file_snippets()
        # Must have header, ### heading with path:line, python fence
        assert result.startswith("## Failure-Site Snippets")
        assert f"### {src}:5" in result
        assert "```python" in result
        assert "```" in result

    def test_uses_last_line_no_match(self, tmp_path: Path):
        """When the traceback mentions the same file twice, the last line wins."""
        src = tmp_path / "multi.py"
        src.write_text("\n".join(f"ln{i}" for i in range(1, 30)) + "\n")
        tb = (
            f'File "{src}", line 3\n'
            f'  inner call\n'
            f'File "{src}", line 20\n'
            f'ValueError: boom'
        )
        h = ErrorHistory()
        h.append(_make_record(file_hint=str(src), traceback_str=tb))

        result = h.get_file_snippets()
        assert ":20" in result

    def test_multiple_records_all_shown(self, tmp_path: Path):
        src1 = tmp_path / "a.py"
        src2 = tmp_path / "b.py"
        src1.write_text("\n".join(f"a{i}" for i in range(1, 20)) + "\n")
        src2.write_text("\n".join(f"b{i}" for i in range(1, 20)) + "\n")

        h = ErrorHistory()
        h.append(_make_record(
            file_hint=str(src1),
            traceback_str=f'File "{src1}", line 5\nError',
        ))
        h.append(_make_record(
            file_hint=str(src2),
            traceback_str=f'File "{src2}", line 10\nError',
        ))

        result = h.get_file_snippets()
        assert str(src1) in result
        assert str(src2) in result

    def test_n_limits_records_checked(self, tmp_path: Path):
        """n=1 means only the most recent record is checked."""
        src = tmp_path / "only.py"
        src.write_text("\n".join(f"r{i}" for i in range(1, 20)) + "\n")

        h = ErrorHistory()
        # Add 5 records — only last one has a real file
        for _ in range(4):
            h.append(_make_record(file_hint="/bad/path.py", traceback_str='File "/bad/path.py", line 1'))
        h.append(_make_record(
            file_hint=str(src),
            traceback_str=f'File "{src}", line 3\nError',
        ))

        result = h.get_file_snippets(n=1)
        assert str(src) in result

    def test_lines_around_respected(self, tmp_path: Path):
        src = tmp_path / "narrow.py"
        src.write_text("\n".join(f"row{i}" for i in range(1, 50)) + "\n")
        tb = f'File "{src}", line 25\nError'
        h = ErrorHistory()
        h.append(_make_record(file_hint=str(src), traceback_str=tb))

        result_narrow = h.get_file_snippets(lines_around=2)
        result_wide = h.get_file_snippets(lines_around=10)
        # Wide should include more rows
        assert len(result_wide) > len(result_narrow)


# ── to_context_str(extended=True) ─────────────────────────────────────────────


class TestToContextStrExtended:
    def _make_record_with_tb(self, tb_lines: int = 20) -> ErrorRecord:
        tb = "\n".join(f"frame_{i}" for i in range(tb_lines))
        return ErrorRecord(
            id="x",
            timestamp=datetime.now(timezone.utc),
            tool_name="bash",
            agent_name="coder",
            error_type="exception",
            message="crash",
            traceback_str=tb,
            file_hint=None,
        )

    def test_extended_header(self):
        h = ErrorHistory()
        h.append(self._make_record_with_tb())
        result = h.to_context_str(n=5, extended=True)
        assert "debug mode" in result.lower()

    def test_normal_header(self):
        h = ErrorHistory()
        h.append(self._make_record_with_tb())
        result = h.to_context_str(n=5, extended=False)
        assert "## Recent Errors\n" in result
        assert "debug mode" not in result.lower()

    def test_extended_shows_more_traceback_lines(self):
        """extended=True shows 15 lines; normal shows 5."""
        tb = "\n".join(f"frame_{i}" for i in range(20))
        h = ErrorHistory()
        h.append(ErrorRecord(
            id="y",
            timestamp=datetime.now(timezone.utc),
            tool_name="bash",
            agent_name="coder",
            error_type="exception",
            message="boom",
            traceback_str=tb,
            file_hint=None,
        ))
        normal = h.to_context_str(extended=False)
        extended = h.to_context_str(extended=True)
        # Count "frame_" occurrences
        normal_count = normal.count("frame_")
        extended_count = extended.count("frame_")
        assert extended_count > normal_count
        assert extended_count <= 15
        assert normal_count <= 5

    def test_empty_returns_empty_regardless_of_extended(self):
        h = ErrorHistory()
        assert h.to_context_str(extended=True) == ""
        assert h.to_context_str(extended=False) == ""
