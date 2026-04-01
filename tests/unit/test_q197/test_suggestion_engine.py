"""Tests for SuggestionEngine — task 1097."""
from __future__ import annotations

import unittest

from lidco.prompts.suggestion_engine import Suggestion, SuggestionEngine


class TestSuggestionFrozen(unittest.TestCase):
    def test_suggestion_immutable(self):
        s = Suggestion(text="hello", confidence=0.8, source="history")
        with self.assertRaises(AttributeError):
            s.text = "changed"  # type: ignore[misc]

    def test_suggestion_fields(self):
        s = Suggestion(text="t", confidence=0.5, source="ctx")
        self.assertEqual(s.text, "t")
        self.assertEqual(s.confidence, 0.5)
        self.assertEqual(s.source, "ctx")

    def test_suggestion_equality(self):
        a = Suggestion("x", 0.9, "h")
        b = Suggestion("x", 0.9, "h")
        self.assertEqual(a, b)


class TestSuggestionEngineInit(unittest.TestCase):
    def test_defaults(self):
        engine = SuggestionEngine()
        self.assertEqual(engine.history, ())
        self.assertEqual(engine.context, "")

    def test_custom(self):
        engine = SuggestionEngine(history=("a", "b"), context="py")
        self.assertEqual(engine.history, ("a", "b"))
        self.assertEqual(engine.context, "py")


class TestSuggest(unittest.TestCase):
    def test_empty_history_returns_generics(self):
        results = SuggestionEngine().suggest(n=3)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(isinstance(r, Suggestion) for r in results))
        self.assertTrue(all(r.source == "generic" for r in results))

    def test_n_zero(self):
        self.assertEqual(SuggestionEngine().suggest(n=0), ())

    def test_negative_n(self):
        self.assertEqual(SuggestionEngine().suggest(n=-1), ())

    def test_history_based(self):
        engine = SuggestionEngine(history=("fix bug", "add tests"))
        results = engine.suggest(n=2)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.source == "history" for r in results))

    def test_context_suggestions(self):
        engine = SuggestionEngine(context="Python FastAPI project")
        results = engine.suggest(n=10)
        sources = {r.source for r in results}
        self.assertIn("context", sources)

    def test_confidence_decreases_with_age(self):
        engine = SuggestionEngine(history=("a", "b", "c", "d"))
        results = engine.suggest(n=4)
        confidences = [r.confidence for r in results]
        self.assertEqual(confidences, sorted(confidences, reverse=True))

    def test_returns_tuple(self):
        result = SuggestionEngine().suggest()
        self.assertIsInstance(result, tuple)


class TestAddContext(unittest.TestCase):
    def test_returns_new_instance(self):
        e1 = SuggestionEngine()
        e2 = e1.add_context("python")
        self.assertIsNot(e1, e2)
        self.assertEqual(e1.context, "")
        self.assertEqual(e2.context, "python")

    def test_merges_context(self):
        e = SuggestionEngine(context="A").add_context("B")
        self.assertEqual(e.context, "A B")


class TestAddHistory(unittest.TestCase):
    def test_returns_new_instance(self):
        e1 = SuggestionEngine()
        e2 = e1.add_history("hello")
        self.assertIsNot(e1, e2)
        self.assertEqual(e1.history, ())
        self.assertEqual(e2.history, ("hello",))

    def test_preserves_context(self):
        e = SuggestionEngine(context="ctx").add_history("h")
        self.assertEqual(e.context, "ctx")
        self.assertEqual(e.history, ("h",))

    def test_chaining(self):
        e = SuggestionEngine().add_history("a").add_history("b")
        self.assertEqual(e.history, ("a", "b"))


if __name__ == "__main__":
    unittest.main()
