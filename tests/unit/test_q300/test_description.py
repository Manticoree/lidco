"""Tests for PRDescriptionGenerator (Q300)."""
import unittest

from lidco.pr.description import PRDescriptionGenerator, PRDescription


SAMPLE_DIFF = """\
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,5 @@
+import os
+import sys
 def main():
     pass
--- a/tests/test_app.py
+++ b/tests/test_app.py
@@ -1,2 +1,4 @@
+def test_new():
+    assert True
 def test_main():
     pass
"""

EMPTY_DIFF = ""


class TestPRDescriptionGenerator(unittest.TestCase):

    def test_summary_single_file(self):
        diff = "--- a/foo.py\n+++ b/foo.py\n+line\n"
        gen = PRDescriptionGenerator()
        result = gen.summary(diff)
        self.assertIn("foo.py", result)

    def test_summary_multiple_files(self):
        gen = PRDescriptionGenerator()
        result = gen.summary(SAMPLE_DIFF)
        self.assertIn("src/app.py", result)

    def test_summary_no_changes(self):
        gen = PRDescriptionGenerator()
        result = gen.summary(EMPTY_DIFF)
        self.assertEqual(result, "No changes detected.")

    def test_summary_truncated(self):
        gen = PRDescriptionGenerator(max_summary_length=10)
        diff = "--- a/very_long_filename.py\n+++ b/very_long_filename.py\n+x\n"
        result = gen.summary(diff)
        self.assertLessEqual(len(result), 10)

    def test_changes_list_includes_additions(self):
        gen = PRDescriptionGenerator()
        changes = gen.changes_list(SAMPLE_DIFF)
        has_added = any("added" in c for c in changes)
        self.assertTrue(has_added)

    def test_changes_list_includes_deletions(self):
        diff = "--- a/foo.py\n+++ b/foo.py\n-removed_line\n"
        gen = PRDescriptionGenerator()
        changes = gen.changes_list(diff)
        has_deleted = any("deleted" in c for c in changes)
        self.assertTrue(has_deleted)

    def test_changes_list_includes_modified_files(self):
        gen = PRDescriptionGenerator()
        changes = gen.changes_list(SAMPLE_DIFF)
        has_modified = any("Modified" in c for c in changes)
        self.assertTrue(has_modified)

    def test_test_plan_includes_test_files(self):
        gen = PRDescriptionGenerator()
        plan = gen.test_plan(SAMPLE_DIFF)
        self.assertIn("test_app.py", plan)

    def test_test_plan_includes_source_files(self):
        gen = PRDescriptionGenerator()
        plan = gen.test_plan(SAMPLE_DIFF)
        self.assertIn("src/app.py", plan)

    def test_test_plan_empty_diff(self):
        gen = PRDescriptionGenerator()
        plan = gen.test_plan(EMPTY_DIFF)
        self.assertIn("No specific test plan", plan)

    def test_generate_full_body(self):
        gen = PRDescriptionGenerator()
        body = gen.generate(["feat: add feature"], SAMPLE_DIFF)
        self.assertIn("## Summary", body)
        self.assertIn("## Changes", body)
        self.assertIn("## Test Plan", body)

    def test_template_formats_data(self):
        gen = PRDescriptionGenerator()
        data = {"summary": "Test summary", "changes": ["Change 1"], "test_plan": "Run tests"}
        result = gen.template(data)
        self.assertIn("Test summary", result)
        self.assertIn("Change 1", result)

    def test_add_and_get_template(self):
        gen = PRDescriptionGenerator()
        gen.add_template("custom", "Hello {name}")
        self.assertEqual(gen.get_template("custom"), "Hello {name}")
        self.assertIsNone(gen.get_template("nonexistent"))

    def test_pr_description_dataclass(self):
        desc = PRDescription(summary="s", changes=["c"], test_plan="t", body="b")
        self.assertEqual(desc.summary, "s")
        self.assertEqual(desc.changes, ["c"])


if __name__ == "__main__":
    unittest.main()
