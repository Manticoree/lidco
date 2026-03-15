"""Tests for DiffSummarizer — Task 336."""

from __future__ import annotations

import pytest

from lidco.analysis.diff_summarizer import DiffHunk, DiffSummary, DiffSummarizer


SIMPLE_DIFF = """\
diff --git a/foo.py b/foo.py
index abc..def 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 context
+added line
-removed line
 more context
"""

TWO_FILE_DIFF = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1,2 @@
+new line
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -1,2 +1 @@
-old line
-old line2
+new
"""


class TestDiffHunk:
    def test_frozen(self):
        h = DiffHunk(file_path="x.py", additions=1, deletions=0)
        with pytest.raises((AttributeError, TypeError)):
            h.additions = 5  # type: ignore[misc]


class TestDiffSummaryByFile:
    def test_by_file_merges_hunks(self):
        hunks = [
            DiffHunk("a.py", 2, 1),
            DiffHunk("a.py", 1, 0),
        ]
        summary = DiffSummary(files_changed=1, total_additions=3, total_deletions=1, hunks=hunks)
        by_file = summary.by_file()
        assert "a.py" in by_file
        assert by_file["a.py"].additions == 3
        assert by_file["a.py"].deletions == 1

    def test_by_file_multiple_files(self):
        hunks = [DiffHunk("a.py", 1, 0), DiffHunk("b.py", 2, 3)]
        summary = DiffSummary(files_changed=2, total_additions=3, total_deletions=3, hunks=hunks)
        by_file = summary.by_file()
        assert "a.py" in by_file
        assert "b.py" in by_file


class TestDiffSummarizer:
    def setup_method(self):
        self.ds = DiffSummarizer()

    def test_empty_diff_returns_zero(self):
        result = self.ds.parse("")
        assert result.files_changed == 0
        assert result.total_additions == 0
        assert result.total_deletions == 0

    def test_simple_diff_one_file(self):
        result = self.ds.parse(SIMPLE_DIFF)
        assert result.files_changed == 1
        assert result.total_additions == 1
        assert result.total_deletions == 1

    def test_two_file_diff(self):
        result = self.ds.parse(TWO_FILE_DIFF)
        assert result.files_changed == 2
        assert result.total_additions == 2
        assert result.total_deletions == 2

    def test_hunks_list_populated(self):
        result = self.ds.parse(SIMPLE_DIFF)
        assert len(result.hunks) == 1
        assert result.hunks[0].file_path == "foo.py"

    def test_whitespace_diff_returns_empty(self):
        result = self.ds.parse("   \n")
        assert result.files_changed == 0

    def test_additions_not_counting_plus_plus_plus(self):
        diff = (
            "diff --git a/x.py b/x.py\n"
            "--- a/x.py\n"
            "+++ b/x.py\n"
            "@@ -1 +1,2 @@\n"
            "+added\n"
        )
        result = self.ds.parse(diff)
        assert result.total_additions == 1  # not 2 (the +++ line excluded)

    def test_deletions_not_counting_minus_minus_minus(self):
        diff = (
            "diff --git a/x.py b/x.py\n"
            "--- a/x.py\n"
            "+++ b/x.py\n"
            "@@ -1,2 +1 @@\n"
            "-removed\n"
        )
        result = self.ds.parse(diff)
        assert result.total_deletions == 1  # not 2 (the --- line excluded)

    def test_by_file_on_result(self):
        result = self.ds.parse(TWO_FILE_DIFF)
        by_file = result.by_file()
        assert "a.py" in by_file
        assert "b.py" in by_file
