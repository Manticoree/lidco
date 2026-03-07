"""Tests for FileWriteTool overwrite confirmation — Task 153."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from lidco.tools.file_write import FileWriteTool, _MAX_DIFF_LINES


# ── helpers ───────────────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def tool() -> FileWriteTool:
    return FileWriteTool()


# ── build_diff ────────────────────────────────────────────────────────────────

class TestBuildDiff:
    def test_returns_unified_diff(self):
        diff = FileWriteTool.build_diff("hello\n", "world\n", "f.txt")
        assert "-hello" in diff
        assert "+world" in diff

    def test_empty_when_identical(self):
        diff = FileWriteTool.build_diff("same\n", "same\n", "f.txt")
        assert diff == ""

    def test_includes_path_in_header(self):
        diff = FileWriteTool.build_diff("a\n", "b\n", "src/main.py")
        assert "src/main.py" in diff

    def test_truncates_at_max_lines(self):
        old = "\n".join(f"line{i}" for i in range(200))
        new = "\n".join(f"changed{i}" for i in range(200))
        diff = FileWriteTool.build_diff(old, new, "big.py")
        # _MAX_DIFF_LINES items + 1 truncation message → _MAX_DIFF_LINES separators
        line_count = diff.count("\n")
        assert line_count <= _MAX_DIFF_LINES + 2

    def test_no_diff_for_empty_to_empty(self):
        diff = FileWriteTool.build_diff("", "", "f.txt")
        assert diff == ""

    def test_new_lines_shown(self):
        diff = FileWriteTool.build_diff("", "new content\n", "f.txt")
        assert "+new content" in diff


# ── set_confirm_callback ──────────────────────────────────────────────────────

class TestSetConfirmCallback:
    def test_default_is_none(self, tool):
        assert tool._confirm_callback is None

    def test_set_and_get(self, tool):
        cb = AsyncMock(return_value=True)
        tool.set_confirm_callback(cb)
        assert tool._confirm_callback is cb

    def test_clear_with_none(self, tool):
        tool.set_confirm_callback(AsyncMock())
        tool.set_confirm_callback(None)
        assert tool._confirm_callback is None


# ── _run: new file (no confirmation needed) ───────────────────────────────────

class TestRunNewFile:
    def test_creates_new_file(self, tool, tmp_path):
        p = tmp_path / "new.txt"
        result = _run(tool._run(path=str(p), content="hello"))
        assert result.success
        assert p.read_text() == "hello"

    def test_callback_not_called_for_new_file(self, tool, tmp_path):
        cb = AsyncMock(return_value=True)
        tool.set_confirm_callback(cb)
        p = tmp_path / "fresh.txt"
        _run(tool._run(path=str(p), content="x"))
        cb.assert_not_called()

    def test_creates_parent_dirs(self, tool, tmp_path):
        p = tmp_path / "a" / "b" / "c.txt"
        result = _run(tool._run(path=str(p), content="deep"))
        assert result.success
        assert p.exists()


# ── _run: overwrite with no callback ─────────────────────────────────────────

class TestRunOverwriteNoCallback:
    def test_overwrites_without_asking(self, tool, tmp_path):
        p = tmp_path / "existing.txt"
        p.write_text("old content")
        result = _run(tool._run(path=str(p), content="new content"))
        assert result.success
        assert p.read_text() == "new content"


# ── _run: overwrite with callback confirmed ───────────────────────────────────

class TestRunOverwriteConfirmed:
    def test_writes_when_callback_returns_true(self, tool, tmp_path):
        cb = AsyncMock(return_value=True)
        tool.set_confirm_callback(cb)
        p = tmp_path / "file.txt"
        p.write_text("original")
        result = _run(tool._run(path=str(p), content="updated"))
        assert result.success
        assert p.read_text() == "updated"

    def test_callback_receives_correct_args(self, tool, tmp_path):
        cb = AsyncMock(return_value=True)
        tool.set_confirm_callback(cb)
        p = tmp_path / "file.txt"
        p.write_text("old")
        _run(tool._run(path=str(p), content="new"))
        cb.assert_called_once()
        _, old, new = cb.call_args[0]
        assert old == "old"
        assert new == "new"

    def test_callback_called_with_resolved_path(self, tool, tmp_path):
        cb = AsyncMock(return_value=True)
        tool.set_confirm_callback(cb)
        p = tmp_path / "x.txt"
        p.write_text("x")
        _run(tool._run(path=str(p), content="y"))
        path_arg = cb.call_args[0][0]
        assert Path(path_arg).is_absolute()


# ── _run: overwrite rejected ──────────────────────────────────────────────────

class TestRunOverwriteRejected:
    def test_does_not_write_when_rejected(self, tool, tmp_path):
        cb = AsyncMock(return_value=False)
        tool.set_confirm_callback(cb)
        p = tmp_path / "file.txt"
        p.write_text("original")
        result = _run(tool._run(path=str(p), content="new"))
        assert result.success
        assert p.read_text() == "original"  # unchanged

    def test_returns_cancellation_message(self, tool, tmp_path):
        cb = AsyncMock(return_value=False)
        tool.set_confirm_callback(cb)
        p = tmp_path / "file.txt"
        p.write_text("x")
        result = _run(tool._run(path=str(p), content="y"))
        assert "отменена" in result.output or "cancel" in result.output.lower()

    def test_cancelled_flag_in_metadata(self, tool, tmp_path):
        cb = AsyncMock(return_value=False)
        tool.set_confirm_callback(cb)
        p = tmp_path / "file.txt"
        p.write_text("x")
        result = _run(tool._run(path=str(p), content="y"))
        assert result.metadata.get("cancelled") is True
