"""Tests for DiffEngine and Hunk — T448."""
from __future__ import annotations

import pytest

from lidco.editing.diff_engine import DiffEngine, DiffPreview
from lidco.editing.hunk import Hunk


class TestHunk:
    def test_added_lines(self):
        hunk = Hunk(index=0, header="@@ -1,2 +1,3 @@", lines=[" ctx", "-old", "+new", "+extra"])
        assert hunk.added_lines == ["new", "extra"]

    def test_removed_lines(self):
        hunk = Hunk(index=0, header="@@ -1,2 +1,1 @@", lines=[" ctx", "-old"])
        assert hunk.removed_lines == ["old"]

    def test_str(self):
        hunk = Hunk(index=0, header="@@ -1 +1 @@", lines=["+new"])
        s = str(hunk)
        assert "@@ -1 +1 @@" in s
        assert "+new" in s


class TestDiffEngine:
    def test_no_changes_no_hunks(self):
        engine = DiffEngine()
        preview = engine.preview("f.py", "same\n", "same\n")
        assert not preview.has_changes
        assert preview.hunks == []

    def test_detects_changes(self):
        engine = DiffEngine()
        preview = engine.preview("f.py", "old\n", "new\n")
        assert preview.has_changes
        assert len(preview.hunks) >= 1

    def test_preview_path(self):
        engine = DiffEngine()
        preview = engine.preview("src/foo.py", "a\n", "b\n")
        assert preview.path == "src/foo.py"

    def test_apply_all_accepted(self):
        engine = DiffEngine()
        original = "line1\nline2\n"
        new = "line1\nchanged\n"
        preview = engine.preview("f.py", original, new)
        result = preview.apply(set(range(len(preview.hunks))))
        assert result == new

    def test_apply_none_accepted(self):
        engine = DiffEngine()
        original = "line1\nline2\n"
        new = "line1\nchanged\n"
        preview = engine.preview("f.py", original, new)
        result = preview.apply(set())
        assert result == original

    def test_multiple_hunks(self):
        engine = DiffEngine()
        # Create content with changes far enough apart to generate multiple hunks
        original = "\n".join(["line" + str(i) for i in range(20)]) + "\n"
        lines = original.splitlines()
        lines[0] = "CHANGED_TOP"
        lines[19] = "CHANGED_BOTTOM"
        new = "\n".join(lines) + "\n"
        preview = engine.preview("f.py", original, new)
        # Should have 2 hunks (changes far apart)
        assert len(preview.hunks) >= 1

    def test_hunk_indices_sequential(self):
        engine = DiffEngine()
        original = "\n".join(["line" + str(i) for i in range(20)]) + "\n"
        lines = original.splitlines()
        lines[0] = "A"
        lines[19] = "B"
        new = "\n".join(lines) + "\n"
        preview = engine.preview("f.py", original, new)
        for i, h in enumerate(preview.hunks):
            assert h.index == i

    def test_diff_preview_dataclass(self):
        preview = DiffPreview(path="x.py", original="a", new_content="b", hunks=[])
        assert not preview.has_changes
