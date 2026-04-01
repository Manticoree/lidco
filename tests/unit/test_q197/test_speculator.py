"""Tests for PromptSpeculator — task 1098."""
from __future__ import annotations

import unittest

from lidco.prompts.speculator import PromptSpeculator, Speculation


class TestSpeculationFrozen(unittest.TestCase):
    def test_immutable(self):
        s = Speculation(predicted_query="q", confidence=0.5, prefetch_keys=("a",))
        with self.assertRaises(AttributeError):
            s.predicted_query = "x"  # type: ignore[misc]

    def test_fields(self):
        s = Speculation("q", 0.7, ("k1", "k2"))
        self.assertEqual(s.predicted_query, "q")
        self.assertEqual(s.confidence, 0.7)
        self.assertEqual(s.prefetch_keys, ("k1", "k2"))

    def test_equality(self):
        a = Speculation("q", 0.5, ())
        b = Speculation("q", 0.5, ())
        self.assertEqual(a, b)


class TestPromptSpeculatorInit(unittest.TestCase):
    def test_defaults(self):
        spec = PromptSpeculator()
        self.assertEqual(spec.history, ())

    def test_custom_history(self):
        spec = PromptSpeculator(history=("a", "b"))
        self.assertEqual(spec.history, ("a", "b"))


class TestSpeculate(unittest.TestCase):
    def test_empty_history(self):
        result = PromptSpeculator().speculate()
        self.assertIsInstance(result, Speculation)
        self.assertEqual(result.predicted_query, "")
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.prefetch_keys, ())

    def test_list_pattern(self):
        spec = PromptSpeculator(history=("list all files",))
        result = spec.speculate()
        self.assertGreater(result.confidence, 0.0)
        self.assertIn("results", result.prefetch_keys)

    def test_fix_pattern(self):
        spec = PromptSpeculator(history=("fix the bug",))
        result = spec.speculate()
        self.assertIn("test_results", result.prefetch_keys)

    def test_write_pattern(self):
        spec = PromptSpeculator(history=("write a function",))
        result = spec.speculate()
        self.assertIn("diff", result.prefetch_keys)

    def test_generic_fallback(self):
        spec = PromptSpeculator(history=("hello world",))
        result = spec.speculate()
        self.assertIn("context", result.prefetch_keys)

    def test_confidence_grows_with_history(self):
        s1 = PromptSpeculator(history=("list x",))
        s2 = PromptSpeculator(history=("list x", "list y", "list z"))
        self.assertGreaterEqual(s2.speculate().confidence, s1.speculate().confidence)


class TestAddHistory(unittest.TestCase):
    def test_returns_new_instance(self):
        s1 = PromptSpeculator()
        s2 = s1.add_history("hi")
        self.assertIsNot(s1, s2)
        self.assertEqual(s1.history, ())
        self.assertEqual(s2.history, ("hi",))

    def test_chaining(self):
        s = PromptSpeculator().add_history("a").add_history("b")
        self.assertEqual(s.history, ("a", "b"))


class TestShouldPrefetch(unittest.TestCase):
    def test_empty_history_no_prefetch(self):
        self.assertFalse(PromptSpeculator().should_prefetch())

    def test_with_high_confidence(self):
        spec = PromptSpeculator(history=("fix the bug", "fix another"))
        self.assertTrue(spec.should_prefetch())

    def test_threshold_boundary(self):
        spec = PromptSpeculator(history=("list items",))
        result = spec.speculate()
        self.assertEqual(spec.should_prefetch(), result.confidence >= 0.3)


if __name__ == "__main__":
    unittest.main()
