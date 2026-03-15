"""Tests for Task 375 — AI conflict resolver."""
from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.tools.conflict_resolver import (
    ConflictBlock,
    apply_resolution,
    find_conflicted_files,
    parse_conflict_blocks,
)


class TestConflictBlock:
    def test_dataclass_fields(self):
        block = ConflictBlock(
            file="foo.py",
            ours="a = 1",
            theirs="a = 2",
            context_before="# before",
            context_after="# after",
            start_line=5,
        )
        assert block.file == "foo.py"
        assert block.ours == "a = 1"
        assert block.theirs == "a = 2"
        assert block.context_before == "# before"
        assert block.context_after == "# after"
        assert block.start_line == 5

    def test_default_fields(self):
        block = ConflictBlock(file="x.py", ours="x", theirs="y")
        assert block.context_before == ""
        assert block.context_after == ""
        assert block.start_line == 0


class TestParseConflictBlocks:
    def test_parse_single_conflict(self, tmp_path: Path):
        content = textwrap.dedent("""\
            def foo():
                pass

            <<<<<<< HEAD
                return 1
            =======
                return 2
            >>>>>>> branch
        """)
        f = tmp_path / "test.py"
        f.write_text(content, encoding="utf-8")

        blocks = parse_conflict_blocks(str(f))
        assert len(blocks) == 1
        assert "return 1" in blocks[0].ours
        assert "return 2" in blocks[0].theirs
        assert blocks[0].file == str(f)

    def test_parse_multiple_conflicts(self, tmp_path: Path):
        content = textwrap.dedent("""\
            <<<<<<< HEAD
            a = 1
            =======
            a = 2
            >>>>>>> branch

            <<<<<<< HEAD
            b = 3
            =======
            b = 4
            >>>>>>> branch
        """)
        f = tmp_path / "multi.py"
        f.write_text(content, encoding="utf-8")

        blocks = parse_conflict_blocks(str(f))
        assert len(blocks) == 2
        assert "a = 1" in blocks[0].ours
        assert "b = 3" in blocks[1].ours

    def test_no_conflicts_returns_empty(self, tmp_path: Path):
        f = tmp_path / "clean.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert parse_conflict_blocks(str(f)) == []

    def test_missing_file_returns_empty(self):
        assert parse_conflict_blocks("/nonexistent/file.py") == []

    def test_context_captured(self, tmp_path: Path):
        content = textwrap.dedent("""\
            line_before_1
            line_before_2
            <<<<<<< HEAD
            ours_code
            =======
            theirs_code
            >>>>>>> branch
            line_after_1
        """)
        f = tmp_path / "ctx.py"
        f.write_text(content, encoding="utf-8")

        blocks = parse_conflict_blocks(str(f))
        assert len(blocks) == 1
        assert "line_before" in blocks[0].context_before
        assert "line_after" in blocks[0].context_after

    def test_start_line_recorded(self, tmp_path: Path):
        content = "x = 1\ny = 2\n<<<<<<< HEAD\na\n=======\nb\n>>>>>>> br\n"
        f = tmp_path / "lines.py"
        f.write_text(content, encoding="utf-8")
        blocks = parse_conflict_blocks(str(f))
        assert blocks[0].start_line == 3  # 1-indexed


class TestApplyResolution:
    def test_replaces_conflict(self, tmp_path: Path):
        content = "before\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> br\nafter\n"
        f = tmp_path / "res.py"
        f.write_text(content, encoding="utf-8")

        blocks = parse_conflict_blocks(str(f))
        result = apply_resolution(str(f), blocks, ["resolved_code"])
        assert result is True

        written = f.read_text(encoding="utf-8")
        assert "resolved_code" in written
        assert "<<<<<<" not in written

    def test_returns_false_on_missing_file(self):
        block = ConflictBlock(file="/bad/path.py", ours="x", theirs="y")
        assert apply_resolution("/bad/path.py", [block], ["resolved"]) is False


class TestFindConflictedFiles:
    def test_returns_list(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="foo.py\nbar.py\n")
            result = find_conflicted_files()
        assert "foo.py" in result
        assert "bar.py" in result

    def test_git_not_found_returns_empty(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = find_conflicted_files()
        assert result == []

    def test_empty_output_returns_empty(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = find_conflicted_files()
        assert result == []
