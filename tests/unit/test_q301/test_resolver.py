"""Tests for lidco.merge.resolver."""
from __future__ import annotations

import unittest

from lidco.merge.detector import Conflict
from lidco.merge.resolver import ConflictResolver, Resolution


class TestResolution(unittest.TestCase):
    def test_fields(self):
        c = Conflict(file_path="a.py", line_start=0, line_end=0, text_a="x", text_b="y")
        r = Resolution(conflict=c, strategy="ours", resolved_text="x")
        self.assertEqual(r.strategy, "ours")
        self.assertEqual(r.confidence, 0.0)
        self.assertEqual(r.explanation, "")


class TestConflictResolver(unittest.TestCase):
    def setUp(self):
        self.resolver = ConflictResolver()
        self.conflict = Conflict(
            file_path="f.py",
            line_start=1,
            line_end=3,
            text_a="def foo():\n    return 1\n",
            text_b="def foo():\n    return 2\n",
        )

    def test_resolve_ours(self):
        r = self.resolver.resolve(self.conflict, strategy="ours")
        self.assertEqual(r.resolved_text, self.conflict.text_a)
        self.assertEqual(r.strategy, "ours")
        self.assertEqual(r.confidence, 1.0)

    def test_resolve_theirs(self):
        r = self.resolver.resolve(self.conflict, strategy="theirs")
        self.assertEqual(r.resolved_text, self.conflict.text_b)
        self.assertEqual(r.strategy, "theirs")

    def test_resolve_union(self):
        r = self.resolver.resolve(self.conflict, strategy="union")
        self.assertIn(self.conflict.text_a, r.resolved_text)
        self.assertIn(self.conflict.text_b, r.resolved_text)
        self.assertEqual(r.strategy, "union")

    def test_resolve_smart(self):
        r = self.resolver.resolve(self.conflict, strategy="smart")
        self.assertEqual(r.strategy, "smart")
        self.assertGreater(r.confidence, 0)

    def test_resolve_default_is_smart(self):
        r = self.resolver.resolve(self.conflict)
        self.assertEqual(r.strategy, "smart")

    def test_suggest_returns_list(self):
        suggestions = self.resolver.suggest(self.conflict)
        self.assertIsInstance(suggestions, list)
        self.assertGreater(len(suggestions), 0)
        self.assertIn("ours", suggestions)
        self.assertIn("theirs", suggestions)

    def test_suggest_similar_content(self):
        c = Conflict(
            file_path="f.py", line_start=0, line_end=0,
            text_a="hello world", text_b="hello world!",
        )
        suggestions = self.resolver.suggest(c)
        self.assertEqual(suggestions[0], "smart")

    def test_preview_contains_strategy(self):
        preview = self.resolver.preview(self.conflict, "ours")
        self.assertIn("ours", preview)
        self.assertIn("100.0%", preview)

    def test_auto_resolve_whitespace_only(self):
        c = Conflict(
            file_path="f.py", line_start=0, line_end=0,
            text_a="hello\n", text_b="  hello  \n",
        )
        resolutions = self.resolver.auto_resolve([c])
        self.assertEqual(len(resolutions), 1)
        self.assertEqual(resolutions[0].strategy, "ours")
        self.assertEqual(resolutions[0].confidence, 1.0)

    def test_auto_resolve_complex(self):
        resolutions = self.resolver.auto_resolve([self.conflict])
        self.assertEqual(len(resolutions), 1)
        self.assertEqual(resolutions[0].strategy, "smart")

    def test_auto_resolve_multiple(self):
        c2 = Conflict(
            file_path="g.py", line_start=0, line_end=0,
            text_a="same", text_b="  same  ",
        )
        resolutions = self.resolver.auto_resolve([self.conflict, c2])
        self.assertEqual(len(resolutions), 2)

    def test_smart_superset_a(self):
        c = Conflict(
            file_path="f.py", line_start=0, line_end=0,
            text_a="line1\nline2\nline3\n",
            text_b="line1\nline2\n",
        )
        r = self.resolver.resolve(c, strategy="smart")
        self.assertEqual(r.resolved_text, c.text_a)
        self.assertIn("superset", r.explanation.lower())


if __name__ == "__main__":
    unittest.main()
