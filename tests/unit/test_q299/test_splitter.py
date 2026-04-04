"""Tests for CommitSplitter (Q299)."""
import unittest

from lidco.smartgit.splitter import (
    CommitSplitter,
    FileGroup,
    FeatureGroup,
    CommitGroup,
)


_MULTI_DIFF = """\
diff --git a/src/lidco/auth/login.py b/src/lidco/auth/login.py
--- a/src/lidco/auth/login.py
+++ b/src/lidco/auth/login.py
@@ -1 +1,2 @@
+pass
diff --git a/tests/unit/test_auth/test_login.py b/tests/unit/test_auth/test_login.py
--- a/tests/unit/test_auth/test_login.py
+++ b/tests/unit/test_auth/test_login.py
@@ -1 +1,2 @@
+pass
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1,2 @@
+updated
"""

_SINGLE_DIFF = """\
diff --git a/src/lidco/core/app.py b/src/lidco/core/app.py
--- a/src/lidco/core/app.py
+++ b/src/lidco/core/app.py
@@ -1 +1,2 @@
+pass
"""


class TestCommitSplitter(unittest.TestCase):
    def setUp(self):
        self.splitter = CommitSplitter()

    # -- split_by_file --------------------------------------------------

    def test_split_by_file_groups_same_dir(self):
        files = ["src/a/foo.py", "src/a/bar.py", "src/b/baz.py"]
        groups = self.splitter.split_by_file(files)
        dirs = [g.directory for g in groups]
        self.assertIn("src/a", dirs)
        self.assertIn("src/b", dirs)

    def test_split_by_file_returns_filegroup(self):
        groups = self.splitter.split_by_file(["x.py"])
        self.assertIsInstance(groups[0], FileGroup)

    def test_split_by_file_root_dir(self):
        groups = self.splitter.split_by_file(["setup.py"])
        self.assertEqual(groups[0].directory, ".")

    def test_split_by_file_sorted_files(self):
        files = ["d/c.py", "d/a.py", "d/b.py"]
        groups = self.splitter.split_by_file(files)
        self.assertEqual(groups[0].files, ["d/a.py", "d/b.py", "d/c.py"])

    def test_split_by_file_empty(self):
        groups = self.splitter.split_by_file([])
        self.assertEqual(groups, [])

    # -- split_by_feature -----------------------------------------------

    def test_split_by_feature_test_group(self):
        files = ["tests/test_foo.py", "src/foo.py"]
        groups = self.splitter.split_by_feature(files)
        features = [g.feature for g in groups]
        self.assertIn("test", features)

    def test_split_by_feature_docs_group(self):
        files = ["README.md", "src/foo.py"]
        groups = self.splitter.split_by_feature(files)
        features = [g.feature for g in groups]
        self.assertIn("docs", features)

    def test_split_by_feature_code_fallback(self):
        files = ["src/foo.py", "src/bar.py"]
        groups = self.splitter.split_by_feature(files)
        features = [g.feature for g in groups]
        self.assertIn("code", features)

    def test_split_by_feature_returns_featuregroup(self):
        groups = self.splitter.split_by_feature(["src/foo.py"])
        self.assertIsInstance(groups[0], FeatureGroup)

    # -- suggest_splits -------------------------------------------------

    def test_suggest_splits_single_file_no_split(self):
        groups = self.splitter.suggest_splits(_SINGLE_DIFF)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].label, "single")

    def test_suggest_splits_multi_file(self):
        groups = self.splitter.suggest_splits(_MULTI_DIFF)
        self.assertGreater(len(groups), 1)

    def test_suggest_splits_returns_commit_groups(self):
        groups = self.splitter.suggest_splits(_MULTI_DIFF)
        for g in groups:
            self.assertIsInstance(g, CommitGroup)

    def test_suggest_splits_has_reason(self):
        groups = self.splitter.suggest_splits(_MULTI_DIFF)
        for g in groups:
            self.assertTrue(g.reason)

    def test_suggest_splits_empty_diff(self):
        groups = self.splitter.suggest_splits("")
        # No files → single group
        self.assertEqual(len(groups), 1)


if __name__ == "__main__":
    unittest.main()
