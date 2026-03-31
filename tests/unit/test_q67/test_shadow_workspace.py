"""Tests for shadow workspace / dry-run mode (Q67 Task 454)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.shadow.workspace import ShadowApplyResult, PendingWrite, ShadowWorkspace


class TestShadowWorkspaceActiveFlag:
    """Test enable/disable/active property."""

    def test_initially_inactive(self) -> None:
        sw = ShadowWorkspace()
        assert sw.active is False

    def test_enable_sets_active(self) -> None:
        sw = ShadowWorkspace()
        sw.enable()
        assert sw.active is True

    def test_disable_sets_inactive(self) -> None:
        sw = ShadowWorkspace()
        sw.enable()
        sw.disable()
        assert sw.active is False

    def test_double_enable_idempotent(self) -> None:
        sw = ShadowWorkspace()
        sw.enable()
        sw.enable()
        assert sw.active is True


class TestIntercept:
    """Test intercept() stores pending writes without touching disk."""

    def test_intercept_does_not_write_to_disk(self, tmp_path: Path) -> None:
        target = tmp_path / "hello.txt"
        sw = ShadowWorkspace()
        sw.enable()
        sw.intercept(str(target), "new content")
        assert not target.exists()

    def test_intercept_adds_to_pending(self, tmp_path: Path) -> None:
        target = tmp_path / "hello.txt"
        sw = ShadowWorkspace()
        sw.intercept(str(target), "new content")
        assert str(target) in sw.pending_paths()

    def test_intercept_captures_original_for_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "existing.txt"
        target.write_text("old content", encoding="utf-8")
        sw = ShadowWorkspace()
        sw.intercept(str(target), "new content")
        pw = sw._pending[str(target)]
        assert pw.original_content == "old content"
        assert pw.new_content == "new content"

    def test_intercept_none_original_for_new_file(self, tmp_path: Path) -> None:
        target = tmp_path / "brand_new.txt"
        sw = ShadowWorkspace()
        sw.intercept(str(target), "content")
        pw = sw._pending[str(target)]
        assert pw.original_content is None

    def test_intercept_overwrites_previous_pending(self, tmp_path: Path) -> None:
        target = tmp_path / "f.txt"
        sw = ShadowWorkspace()
        sw.intercept(str(target), "v1")
        sw.intercept(str(target), "v2")
        assert sw._pending[str(target)].new_content == "v2"
        assert len(sw.pending_paths()) == 1


class TestGetDiff:
    """Test unified diff generation."""

    def test_get_diff_new_file(self, tmp_path: Path) -> None:
        target = tmp_path / "new.py"
        sw = ShadowWorkspace()
        sw.intercept(str(target), "line1\nline2\n")
        diff = sw.get_diff(str(target))
        assert "+line1" in diff
        assert "+line2" in diff

    def test_get_diff_modified_file(self, tmp_path: Path) -> None:
        target = tmp_path / "mod.py"
        target.write_text("old line\n", encoding="utf-8")
        sw = ShadowWorkspace()
        sw.intercept(str(target), "new line\n")
        diff = sw.get_diff(str(target))
        assert "-old line" in diff
        assert "+new line" in diff

    def test_get_diff_specific_path(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        sw = ShadowWorkspace()
        sw.intercept(str(f1), "aaa\n")
        sw.intercept(str(f2), "bbb\n")
        diff = sw.get_diff(str(f1))
        assert "a.py" in diff
        assert "b.py" not in diff

    def test_get_diff_all_files(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        sw = ShadowWorkspace()
        sw.intercept(str(f1), "aaa\n")
        sw.intercept(str(f2), "bbb\n")
        diff = sw.get_diff()
        assert "a.py" in diff
        assert "b.py" in diff

    def test_get_diff_nonexistent_path_returns_empty(self) -> None:
        sw = ShadowWorkspace()
        assert sw.get_diff("/no/such/path") == ""


class TestApply:
    """Test apply() writes pending changes to disk."""

    def test_apply_writes_to_disk(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        sw = ShadowWorkspace()
        sw.intercept(str(target), "hello world")
        result = sw.apply()
        assert target.read_text(encoding="utf-8") == "hello world"
        assert str(target) in result.applied

    def test_apply_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "sub" / "deep" / "file.txt"
        sw = ShadowWorkspace()
        sw.intercept(str(target), "nested")
        result = sw.apply()
        assert target.read_text(encoding="utf-8") == "nested"
        assert str(target) in result.applied

    def test_apply_removes_from_pending(self, tmp_path: Path) -> None:
        target = tmp_path / "f.txt"
        sw = ShadowWorkspace()
        sw.intercept(str(target), "data")
        sw.apply()
        assert len(sw.pending_paths()) == 0

    def test_apply_specific_paths(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        sw = ShadowWorkspace()
        sw.intercept(str(f1), "aaa")
        sw.intercept(str(f2), "bbb")
        result = sw.apply([str(f1)])
        assert f1.read_text(encoding="utf-8") == "aaa"
        assert not f2.exists()
        assert str(f1) in result.applied
        assert str(f2) not in result.applied
        assert str(f2) in sw.pending_paths()

    def test_apply_skips_unknown_paths(self, tmp_path: Path) -> None:
        sw = ShadowWorkspace()
        result = sw.apply(["/no/such/pending"])
        assert "/no/such/pending" in result.skipped
        assert len(result.applied) == 0

    def test_apply_result_has_correct_structure(self, tmp_path: Path) -> None:
        target = tmp_path / "f.txt"
        sw = ShadowWorkspace()
        sw.intercept(str(target), "data")
        result = sw.apply()
        assert isinstance(result, ShadowApplyResult)
        assert isinstance(result.applied, list)
        assert isinstance(result.skipped, list)
        assert isinstance(result.errors, dict)


class TestDiscard:
    """Test discard() clears pending changes."""

    def test_discard_all(self, tmp_path: Path) -> None:
        sw = ShadowWorkspace()
        sw.intercept(str(tmp_path / "a.txt"), "a")
        sw.intercept(str(tmp_path / "b.txt"), "b")
        count = sw.discard()
        assert count == 2
        assert len(sw.pending_paths()) == 0

    def test_discard_specific_paths(self, tmp_path: Path) -> None:
        f1 = str(tmp_path / "a.txt")
        f2 = str(tmp_path / "b.txt")
        sw = ShadowWorkspace()
        sw.intercept(f1, "a")
        sw.intercept(f2, "b")
        count = sw.discard([f1])
        assert count == 1
        assert f1 not in sw.pending_paths()
        assert f2 in sw.pending_paths()

    def test_discard_nonexistent_path_returns_zero(self) -> None:
        sw = ShadowWorkspace()
        count = sw.discard(["/no/such/path"])
        assert count == 0

    def test_discard_empty_workspace(self) -> None:
        sw = ShadowWorkspace()
        count = sw.discard()
        assert count == 0


class TestSummary:
    """Test human-readable summary."""

    def test_summary_no_pending(self) -> None:
        sw = ShadowWorkspace()
        assert sw.summary() == "No pending changes."

    def test_summary_with_one_file(self, tmp_path: Path) -> None:
        sw = ShadowWorkspace()
        sw.intercept(str(tmp_path / "foo.py"), "x")
        s = sw.summary()
        assert "1 file(s) pending" in s
        assert "foo.py" in s

    def test_summary_truncates_at_five(self, tmp_path: Path) -> None:
        sw = ShadowWorkspace()
        for i in range(7):
            sw.intercept(str(tmp_path / f"file{i}.py"), f"content{i}")
        s = sw.summary()
        assert "7 file(s) pending" in s
        assert "+2 more" in s


class TestPendingWriteDataclass:
    """Test PendingWrite dataclass."""

    def test_fields(self) -> None:
        pw = PendingWrite(path="/tmp/x", new_content="hello", original_content="old")
        assert pw.path == "/tmp/x"
        assert pw.new_content == "hello"
        assert pw.original_content == "old"

    def test_none_original(self) -> None:
        pw = PendingWrite(path="/tmp/x", new_content="hello", original_content=None)
        assert pw.original_content is None


class TestFileWriteToolShadowIntegration:
    """Test FileWriteTool respects shadow workspace."""

    def test_write_tool_intercepts_when_shadow_active(self, tmp_path: Path) -> None:
        from lidco.tools.file_write import FileWriteTool

        sw = ShadowWorkspace()
        sw.enable()
        tool = FileWriteTool()
        tool.set_shadow_workspace(sw)

        target = tmp_path / "output.txt"
        result = asyncio.run(tool._run(path=str(target), content="shadow content"))
        assert result.success is True
        assert "dry-run" in result.output.lower() or "staged" in result.output.lower()
        assert not target.exists()
        assert str(target.resolve()) in sw.pending_paths() or str(target) in sw.pending_paths()

    def test_write_tool_writes_normally_when_shadow_inactive(self, tmp_path: Path) -> None:
        from lidco.tools.file_write import FileWriteTool

        sw = ShadowWorkspace()  # not enabled
        tool = FileWriteTool()
        tool.set_shadow_workspace(sw)

        target = tmp_path / "output.txt"
        result = asyncio.run(tool._run(path=str(target), content="real content"))
        assert result.success is True
        assert target.read_text(encoding="utf-8") == "real content"

    def test_write_tool_writes_normally_without_shadow(self, tmp_path: Path) -> None:
        from lidco.tools.file_write import FileWriteTool

        tool = FileWriteTool()
        target = tmp_path / "output.txt"
        result = asyncio.run(tool._run(path=str(target), content="real content"))
        assert result.success is True
        assert target.read_text(encoding="utf-8") == "real content"


class TestFileEditToolShadowIntegration:
    """Test FileEditTool respects shadow workspace."""

    def test_edit_tool_intercepts_when_shadow_active(self, tmp_path: Path) -> None:
        from lidco.tools.file_edit import FileEditTool

        target = tmp_path / "src.py"
        target.write_text("hello world", encoding="utf-8")

        sw = ShadowWorkspace()
        sw.enable()
        tool = FileEditTool()
        tool.set_shadow_workspace(sw)

        result = asyncio.run(
            tool._run(path=str(target), old_string="hello", new_string="goodbye")
        )
        assert result.success is True
        assert "dry-run" in result.output.lower() or "staged" in result.output.lower()
        # Original file unchanged
        assert target.read_text(encoding="utf-8") == "hello world"

    def test_edit_tool_edits_normally_when_shadow_inactive(self, tmp_path: Path) -> None:
        from lidco.tools.file_edit import FileEditTool

        target = tmp_path / "src.py"
        target.write_text("hello world", encoding="utf-8")

        sw = ShadowWorkspace()  # not enabled
        tool = FileEditTool()
        tool.set_shadow_workspace(sw)

        result = asyncio.run(
            tool._run(path=str(target), old_string="hello", new_string="goodbye")
        )
        assert result.success is True
        assert target.read_text(encoding="utf-8") == "goodbye world"
