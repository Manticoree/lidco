"""Tests for Q144 CompatChecker."""
from __future__ import annotations

import unittest

from lidco.config.compat_checker import CompatChecker, CompatIssue, CompatResult


class TestCompatIssue(unittest.TestCase):
    def test_fields(self):
        issue = CompatIssue(field="x", issue_type="removed", message="gone", severity="error")
        self.assertEqual(issue.field, "x")
        self.assertEqual(issue.issue_type, "removed")
        self.assertEqual(issue.severity, "error")


class TestCompatResult(unittest.TestCase):
    def test_defaults(self):
        r = CompatResult(compatible=True)
        self.assertEqual(r.issues, [])
        self.assertEqual(r.suggestions, [])


class TestCompatChecker(unittest.TestCase):
    def setUp(self):
        self.cc = CompatChecker()

    # --- add_removed ---

    def test_removed_field_detected(self):
        self.cc.add_removed("old_key", "2.0.0")
        result = self.cc.check({"old_key": 1})
        self.assertFalse(result.compatible)
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].issue_type, "removed")
        self.assertEqual(result.issues[0].severity, "error")

    def test_removed_field_not_present(self):
        self.cc.add_removed("old_key", "2.0.0")
        result = self.cc.check({"new_key": 1})
        self.assertTrue(result.compatible)
        self.assertEqual(len(result.issues), 0)

    def test_removed_with_alternative(self):
        self.cc.add_removed("old_key", "2.0.0", alternative="new_key")
        result = self.cc.check({"old_key": 1})
        self.assertIn("new_key", result.issues[0].message)
        self.assertGreater(len(result.suggestions), 0)

    # --- add_renamed ---

    def test_renamed_field_detected(self):
        self.cc.add_renamed("old_name", "new_name", "2.0.0")
        result = self.cc.check({"old_name": "val"})
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].issue_type, "renamed")
        self.assertEqual(result.issues[0].severity, "warning")

    def test_renamed_not_present(self):
        self.cc.add_renamed("old_name", "new_name", "2.0.0")
        result = self.cc.check({"new_name": "val"})
        self.assertTrue(result.compatible)

    def test_renamed_suggestion(self):
        self.cc.add_renamed("old_name", "new_name", "2.0.0")
        result = self.cc.check({"old_name": "val"})
        self.assertTrue(any("new_name" in s for s in result.suggestions))

    # --- add_deprecated ---

    def test_deprecated_field_detected(self):
        self.cc.add_deprecated("legacy", "Will be removed in 3.0.0")
        result = self.cc.check({"legacy": True})
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].issue_type, "deprecated")
        self.assertEqual(result.issues[0].severity, "warning")

    def test_deprecated_not_present(self):
        self.cc.add_deprecated("legacy", "msg")
        result = self.cc.check({"other": 1})
        self.assertEqual(len(result.issues), 0)

    # --- compatible flag ---

    def test_compatible_with_warnings_only(self):
        self.cc.add_deprecated("legacy", "will go away")
        result = self.cc.check({"legacy": True})
        self.assertTrue(result.compatible)  # warnings don't break compat

    def test_incompatible_with_errors(self):
        self.cc.add_removed("bad", "2.0.0")
        result = self.cc.check({"bad": 1})
        self.assertFalse(result.compatible)

    # --- nested fields ---

    def test_nested_removed(self):
        self.cc.add_removed("db.host", "2.0.0")
        result = self.cc.check({"db": {"host": "localhost"}})
        self.assertEqual(len(result.issues), 1)

    def test_nested_renamed(self):
        self.cc.add_renamed("db.host", "database.hostname", "2.0.0")
        result = self.cc.check({"db": {"host": "localhost"}})
        self.assertEqual(result.issues[0].issue_type, "renamed")

    # --- auto_fix ---

    def test_auto_fix_renames(self):
        self.cc.add_renamed("old", "new", "2.0.0")
        fixed, actions = self.cc.auto_fix({"old": "value"})
        self.assertEqual(fixed.get("new"), "value")
        self.assertNotIn("old", fixed)
        self.assertEqual(len(actions), 1)

    def test_auto_fix_removes(self):
        self.cc.add_removed("gone", "2.0.0")
        fixed, actions = self.cc.auto_fix({"gone": 1, "keep": 2})
        self.assertNotIn("gone", fixed)
        self.assertEqual(fixed["keep"], 2)

    def test_auto_fix_no_changes(self):
        self.cc.add_removed("gone", "2.0.0")
        fixed, actions = self.cc.auto_fix({"keep": 1})
        self.assertEqual(len(actions), 0)

    def test_auto_fix_does_not_mutate_original(self):
        self.cc.add_renamed("old", "new", "2.0.0")
        data = {"old": "value"}
        self.cc.auto_fix(data)
        self.assertIn("old", data)


if __name__ == "__main__":
    unittest.main()
