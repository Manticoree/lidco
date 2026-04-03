"""Tests for CompletionEngine (Q251)."""
from __future__ import annotations

import unittest

from lidco.completion.engine import CompletionEngine, CompletionItem


class TestCompletionItem(unittest.TestCase):
    def test_defaults(self):
        item = CompletionItem(text="foo", kind="function")
        self.assertEqual(item.text, "foo")
        self.assertEqual(item.kind, "function")
        self.assertEqual(item.score, 0.0)
        self.assertEqual(item.detail, "")

    def test_frozen(self):
        item = CompletionItem(text="x", kind="var")
        with self.assertRaises(AttributeError):
            item.text = "y"  # type: ignore[misc]


class TestAddSymbol(unittest.TestCase):
    def test_add_symbol_increases_count(self):
        engine = CompletionEngine()
        engine.add_symbol("print", "function")
        self.assertEqual(engine.stats()["symbols"], 1)

    def test_add_multiple_symbols(self):
        engine = CompletionEngine()
        engine.add_symbol("print", "function")
        engine.add_symbol("len", "function")
        engine.add_symbol("str", "class")
        self.assertEqual(engine.stats()["symbols"], 3)

    def test_add_symbol_with_detail(self):
        engine = CompletionEngine()
        engine.add_symbol("open", "function", detail="Open a file")
        items = engine.complete("op")
        self.assertEqual(items[0].detail, "Open a file")


class TestComplete(unittest.TestCase):
    def setUp(self):
        self.engine = CompletionEngine()
        self.engine.add_symbol("print", "function")
        self.engine.add_symbol("property", "decorator")
        self.engine.add_symbol("process", "function")
        self.engine.add_symbol("len", "function")

    def test_prefix_match(self):
        items = self.engine.complete("pr")
        names = [i.text for i in items]
        self.assertIn("print", names)
        self.assertIn("property", names)
        self.assertIn("process", names)
        self.assertNotIn("len", names)

    def test_empty_prefix_returns_empty(self):
        self.assertEqual(self.engine.complete(""), [])

    def test_no_match(self):
        self.assertEqual(self.engine.complete("xyz"), [])

    def test_case_insensitive(self):
        self.engine.add_symbol("MyClass", "class")
        items = self.engine.complete("myc")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].text, "MyClass")

    def test_limit(self):
        for i in range(20):
            self.engine.add_symbol(f"var_{i}", "variable")
        items = self.engine.complete("var", limit=5)
        self.assertEqual(len(items), 5)

    def test_sorted_by_score_desc(self):
        items = self.engine.complete("pr")
        scores = [i.score for i in items]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_increments_query_count(self):
        self.engine.complete("pr")
        self.engine.complete("le")
        self.assertEqual(self.engine.stats()["queries"], 2)

    def test_exact_case_match_scored_higher(self):
        self.engine.add_symbol("Print", "class")
        items = self.engine.complete("Pr")
        # "Print" should score higher than "print" for prefix "Pr"
        names = [i.text for i in items]
        self.assertIn("Print", names)


class TestContext(unittest.TestCase):
    def test_add_context(self):
        engine = CompletionEngine()
        engine.add_context({"current_file": "main.py"})
        self.assertEqual(engine.stats()["context_keys"], 1)

    def test_context_merges(self):
        engine = CompletionEngine()
        engine.add_context({"a": 1})
        engine.add_context({"b": 2})
        self.assertEqual(engine.stats()["context_keys"], 2)

    def test_preferred_kind_boost(self):
        engine = CompletionEngine()
        engine.add_symbol("parse_int", "function")
        engine.add_symbol("Parser", "class")
        engine.add_context({"preferred_kind": "class"})
        items = engine.complete("Par")
        # Parser (class) should be boosted
        self.assertEqual(items[0].text, "Parser")


class TestStats(unittest.TestCase):
    def test_initial_stats(self):
        engine = CompletionEngine()
        s = engine.stats()
        self.assertEqual(s["symbols"], 0)
        self.assertEqual(s["queries"], 0)
        self.assertEqual(s["context_keys"], 0)


if __name__ == "__main__":
    unittest.main()
