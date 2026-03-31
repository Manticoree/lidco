"""Tests for ChangeExplainer — semantic change analysis."""
from __future__ import annotations

import unittest

from lidco.ui.change_explainer import ChangeExplainer, ChangeDetail, ChangeExplanation


class TestChangeExplainerBasic(unittest.TestCase):
    def setUp(self):
        self.explainer = ChangeExplainer()

    def test_no_changes(self):
        result = self.explainer.explain("hello", "hello")
        self.assertEqual(result.summary, "No changes detected.")
        self.assertEqual(len(result.changes), 0)

    def test_empty_old_text(self):
        result = self.explainer.explain("", "new content\nhere")
        self.assertEqual(result.intent, "feature")
        self.assertEqual(len(result.changes), 1)
        self.assertEqual(result.changes[0].kind, "add")

    def test_empty_new_text(self):
        result = self.explainer.explain("old content\nhere", "")
        self.assertEqual(result.intent, "cleanup")
        self.assertEqual(result.changes[0].kind, "remove")

    def test_both_empty(self):
        result = self.explainer.explain("", "")
        self.assertEqual(result.summary, "No changes detected.")

    def test_whitespace_only_old(self):
        result = self.explainer.explain("   \n  ", "new content")
        self.assertEqual(result.intent, "feature")

    def test_whitespace_only_new(self):
        result = self.explainer.explain("old content", "  \n  ")
        self.assertEqual(result.intent, "cleanup")


class TestChangeExplainerAdds(unittest.TestCase):
    def setUp(self):
        self.explainer = ChangeExplainer()

    def test_single_line_add(self):
        result = self.explainer.explain("a\nb", "a\nb\nc")
        kinds = [c.kind for c in result.changes]
        self.assertIn("add", kinds)

    def test_multi_line_add(self):
        result = self.explainer.explain("a", "a\nb\nc\nd")
        self.assertTrue(any(c.kind == "add" for c in result.changes))

    def test_add_intent_is_feature(self):
        result = self.explainer.explain("a", "a\nb\nc")
        self.assertEqual(result.intent, "feature")

    def test_add_has_line_range(self):
        result = self.explainer.explain("a", "a\nb")
        for c in result.changes:
            if c.kind == "add":
                self.assertIsInstance(c.line_range, tuple)
                self.assertEqual(len(c.line_range), 2)


class TestChangeExplainerRemoves(unittest.TestCase):
    def setUp(self):
        self.explainer = ChangeExplainer()

    def test_single_line_remove(self):
        result = self.explainer.explain("a\nb\nc", "a\nc")
        kinds = [c.kind for c in result.changes]
        self.assertIn("remove", kinds)

    def test_multi_line_remove(self):
        result = self.explainer.explain("a\nb\nc\nd", "a")
        self.assertTrue(any(c.kind == "remove" for c in result.changes))

    def test_remove_only_intent_is_cleanup(self):
        result = self.explainer.explain("a\nb\nc", "a")
        self.assertEqual(result.intent, "cleanup")


class TestChangeExplainerModify(unittest.TestCase):
    def setUp(self):
        self.explainer = ChangeExplainer()

    def test_single_modify(self):
        result = self.explainer.explain("hello world", "hello python")
        kinds = [c.kind for c in result.changes]
        self.assertTrue("modify" in kinds or "rename" in kinds)

    def test_modify_preserves_context(self):
        old = "a\nb\nc"
        new = "a\nB\nc"
        result = self.explainer.explain(old, new)
        self.assertEqual(len(result.changes), 1)


class TestChangeExplainerRename(unittest.TestCase):
    def setUp(self):
        self.explainer = ChangeExplainer()

    def test_simple_rename(self):
        old = "def foo():\n    pass"
        new = "def bar():\n    pass"
        result = self.explainer.explain(old, new)
        kinds = [c.kind for c in result.changes]
        self.assertIn("rename", kinds)

    def test_rename_intent_is_refactor(self):
        old = "class Foo:\n    pass"
        new = "class Bar:\n    pass"
        result = self.explainer.explain(old, new)
        self.assertEqual(result.intent, "refactor")


class TestChangeExplainerSummary(unittest.TestCase):
    def setUp(self):
        self.explainer = ChangeExplainer()

    def test_summary_contains_count(self):
        result = self.explainer.explain("a\nb", "a\nc")
        self.assertIn("change", result.summary.lower())

    def test_summary_contains_intent(self):
        result = self.explainer.explain("a", "a\nb")
        self.assertIn("intent", result.summary.lower())

    def test_explanation_dataclass_fields(self):
        result = self.explainer.explain("a", "b")
        self.assertIsInstance(result, ChangeExplanation)
        self.assertIsInstance(result.summary, str)
        self.assertIsInstance(result.changes, list)
        self.assertIsInstance(result.intent, str)


class TestChangeDetail(unittest.TestCase):
    def test_frozen_dataclass(self):
        detail = ChangeDetail(kind="add", description="Added lines", line_range=(1, 5))
        self.assertEqual(detail.kind, "add")
        self.assertEqual(detail.line_range, (1, 5))


if __name__ == "__main__":
    unittest.main()
