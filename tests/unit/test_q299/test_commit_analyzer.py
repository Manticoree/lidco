"""Tests for CommitAnalyzer (Q299)."""
import unittest

from lidco.smartgit.commit_analyzer import CommitAnalyzer, AnalysisResult


_DIFF_FEAT = """\
diff --git a/src/lidco/auth/login.py b/src/lidco/auth/login.py
--- a/src/lidco/auth/login.py
+++ b/src/lidco/auth/login.py
@@ -1,3 +1,5 @@
+# New feature: add OAuth support
+import oauth
 def login():
     pass
"""

_DIFF_FIX = """\
diff --git a/src/lidco/core/session.py b/src/lidco/core/session.py
--- a/src/lidco/core/session.py
+++ b/src/lidco/core/session.py
@@ -10,3 +10,4 @@
-    bug here
+    fix the bug in session
"""

_DIFF_TEST = """\
diff --git a/tests/unit/test_auth/test_login.py b/tests/unit/test_auth/test_login.py
--- a/tests/unit/test_auth/test_login.py
+++ b/tests/unit/test_auth/test_login.py
@@ -1,2 +1,4 @@
+def test_new_case():
+    assert True
"""

_DIFF_DOCS = """\
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1,2 @@
+Updated docs
"""

_DIFF_REFACTOR = """\
diff --git a/src/lidco/cli/app.py b/src/lidco/cli/app.py
--- a/src/lidco/cli/app.py
+++ b/src/lidco/cli/app.py
@@ -5,3 +5,3 @@
-    old name refactor rename
+    new name
"""


class TestCommitAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = CommitAnalyzer()

    # -- classify -------------------------------------------------------

    def test_classify_feat(self):
        self.assertEqual(self.analyzer.classify(_DIFF_FEAT), "feat")

    def test_classify_fix(self):
        self.assertEqual(self.analyzer.classify(_DIFF_FIX), "fix")

    def test_classify_test(self):
        self.assertEqual(self.analyzer.classify(_DIFF_TEST), "test")

    def test_classify_docs(self):
        self.assertEqual(self.analyzer.classify(_DIFF_DOCS), "docs")

    def test_classify_refactor(self):
        self.assertEqual(self.analyzer.classify(_DIFF_REFACTOR), "refactor")

    def test_classify_chore_fallback(self):
        self.assertEqual(self.analyzer.classify("nothing special"), "chore")

    # -- extract_scope --------------------------------------------------

    def test_extract_scope_from_path(self):
        scope = self.analyzer.extract_scope(_DIFF_FEAT)
        self.assertEqual(scope, "auth")

    def test_extract_scope_empty(self):
        scope = self.analyzer.extract_scope("no paths here")
        self.assertEqual(scope, "")

    def test_extract_scope_core(self):
        scope = self.analyzer.extract_scope(_DIFF_FIX)
        self.assertEqual(scope, "core")

    # -- suggest_message ------------------------------------------------

    def test_suggest_message_single_file(self):
        msg = self.analyzer.suggest_message(_DIFF_DOCS)
        self.assertIn("docs", msg)
        self.assertIn("README.md", msg)

    def test_suggest_message_contains_stats(self):
        msg = self.analyzer.suggest_message(_DIFF_FEAT)
        self.assertIn("+", msg)
        self.assertIn("-", msg)

    # -- analyze --------------------------------------------------------

    def test_analyze_returns_result(self):
        result = self.analyzer.analyze(_DIFF_FEAT)
        self.assertIsInstance(result, AnalysisResult)
        self.assertEqual(result.category, "feat")
        self.assertEqual(result.scope, "auth")
        self.assertGreater(result.additions, 0)

    def test_analyze_files_populated(self):
        result = self.analyzer.analyze(_DIFF_FEAT)
        self.assertIn("src/lidco/auth/login.py", result.files)

    def test_analyze_result_immutable(self):
        result = self.analyzer.analyze(_DIFF_FEAT)
        with self.assertRaises(AttributeError):
            result.category = "other"  # type: ignore[misc]

    # -- _extract_files -------------------------------------------------

    def test_extract_files_deduplicates(self):
        files = CommitAnalyzer._extract_files(_DIFF_FEAT)
        self.assertEqual(len(files), len(set(files)))

    def test_extract_files_ignores_dev_null(self):
        diff = "--- /dev/null\n+++ b/newfile.py\n+hello"
        files = CommitAnalyzer._extract_files(diff)
        self.assertNotIn("/dev/null", files)


if __name__ == "__main__":
    unittest.main()
