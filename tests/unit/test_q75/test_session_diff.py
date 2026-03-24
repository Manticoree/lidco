"""Tests for SessionDiffCollector — T497."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from lidco.review.session_diff import FileDiff, SessionDiff, SessionDiffCollector, _parse_unified_diff


SAMPLE_DIFF = """diff --git a/foo.py b/foo.py
index abc..def 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,3 @@
 def foo():
-    pass
+    return 42
"""


class TestSessionDiffCollector:
    def test_collect_from_tracked_changes(self, tmp_path):
        collector = SessionDiffCollector(project_dir=tmp_path)
        collector.track("a.py", "old content\n", "new content\n")
        diff = collector._collect_from_tracked()
        assert diff.has_changes
        assert len(diff.files) == 1

    def test_no_changes_empty_diff(self, tmp_path):
        collector = SessionDiffCollector(project_dir=tmp_path)
        diff = collector._collect_from_tracked()
        assert not diff.has_changes

    def test_additions_counted(self, tmp_path):
        collector = SessionDiffCollector(project_dir=tmp_path)
        collector.track("b.py", "line1\n", "line1\nline2\nline3\n")
        diff = collector._collect_from_tracked()
        assert diff.total_additions >= 2

    def test_deletions_counted(self, tmp_path):
        collector = SessionDiffCollector(project_dir=tmp_path)
        collector.track("c.py", "a\nb\nc\n", "a\n")
        diff = collector._collect_from_tracked()
        assert diff.total_deletions >= 2

    def test_parse_unified_diff(self):
        result = _parse_unified_diff(SAMPLE_DIFF)
        assert result.has_changes
        assert result.files[0].path == "foo.py"

    def test_file_diff_dataclass(self):
        fd = FileDiff(path="x.py", diff="--- a\n+++ b\n", additions=1, deletions=0)
        assert fd.path == "x.py"

    def test_session_diff_has_changes(self):
        sd = SessionDiff(files=[FileDiff(path="x.py", diff="...", additions=1, deletions=0)], total_additions=1, total_deletions=0)
        assert sd.has_changes

    def test_collect_falls_back_to_tracked_on_git_error(self, tmp_path):
        collector = SessionDiffCollector(project_dir=tmp_path)
        collector.track("d.py", "old\n", "new\n")
        with patch("subprocess.run", side_effect=Exception("git not available")):
            diff = collector.collect()
        assert diff.has_changes
