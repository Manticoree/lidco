"""Tests for HistoryAnalyzer — task 1099."""
from __future__ import annotations

import unittest

from lidco.prompts.history_analyzer import HistoryAnalyzer, PromptPattern


class TestPromptPatternFrozen(unittest.TestCase):
    def test_immutable(self):
        p = PromptPattern(pattern="fix", frequency=3, examples=("a",), category="fix")
        with self.assertRaises(AttributeError):
            p.pattern = "x"  # type: ignore[misc]

    def test_fields(self):
        p = PromptPattern("test", 2, ("t1", "t2"), "test")
        self.assertEqual(p.pattern, "test")
        self.assertEqual(p.frequency, 2)
        self.assertEqual(p.examples, ("t1", "t2"))
        self.assertEqual(p.category, "test")

    def test_equality(self):
        a = PromptPattern("p", 1, (), "c")
        b = PromptPattern("p", 1, (), "c")
        self.assertEqual(a, b)


class TestHistoryAnalyzerInit(unittest.TestCase):
    def test_defaults(self):
        a = HistoryAnalyzer()
        self.assertEqual(a.history, ())

    def test_custom(self):
        a = HistoryAnalyzer(history=("a", "b"))
        self.assertEqual(a.history, ("a", "b"))


class TestAnalyze(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(HistoryAnalyzer().analyze(), ())

    def test_single_category(self):
        a = HistoryAnalyzer(history=("fix bug", "fix typo"))
        patterns = a.analyze()
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0].category, "fix")
        self.assertEqual(patterns[0].frequency, 2)

    def test_multiple_categories(self):
        a = HistoryAnalyzer(history=("fix bug", "run tests", "write code"))
        patterns = a.analyze()
        categories = {p.category for p in patterns}
        self.assertIn("fix", categories)
        self.assertIn("test", categories)
        self.assertIn("create", categories)

    def test_sorted_by_frequency(self):
        a = HistoryAnalyzer(history=("fix a", "fix b", "fix c", "test x"))
        patterns = a.analyze()
        freqs = [p.frequency for p in patterns]
        self.assertEqual(freqs, sorted(freqs, reverse=True))

    def test_examples_unique(self):
        a = HistoryAnalyzer(history=("fix bug", "fix bug", "fix bug"))
        patterns = a.analyze()
        self.assertEqual(patterns[0].examples, ("fix bug",))

    def test_returns_tuple(self):
        result = HistoryAnalyzer(history=("a",)).analyze()
        self.assertIsInstance(result, tuple)


class TestFrequentCommands(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(HistoryAnalyzer().frequent_commands(), ())

    def test_n_zero(self):
        self.assertEqual(HistoryAnalyzer(history=("a",)).frequent_commands(n=0), ())

    def test_ordering(self):
        a = HistoryAnalyzer(history=("b", "a", "b", "a", "a"))
        result = a.frequent_commands(n=2)
        self.assertEqual(result[0], "a")
        self.assertEqual(result[1], "b")

    def test_limit(self):
        a = HistoryAnalyzer(history=("x", "y", "z"))
        result = a.frequent_commands(n=1)
        self.assertEqual(len(result), 1)


class TestTimePatterns(unittest.TestCase):
    def test_basic(self):
        a = HistoryAnalyzer()
        ts = ("2026-03-31T14:30:00", "2026-03-31T14:45:00", "2026-03-31T09:00:00")
        result = a.time_patterns(ts)
        self.assertEqual(result["14"], 2)
        self.assertEqual(result["09"], 1)

    def test_empty(self):
        self.assertEqual(HistoryAnalyzer().time_patterns(()), {})

    def test_invalid_timestamps(self):
        result = HistoryAnalyzer().time_patterns(("not-a-timestamp",))
        self.assertEqual(result, {})


class TestWorkflowChains(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(HistoryAnalyzer().workflow_chains(), ())

    def test_no_chains(self):
        a = HistoryAnalyzer(history=("fix bug", "run test", "write code"))
        self.assertEqual(a.workflow_chains(), ())

    def test_detects_chain(self):
        a = HistoryAnalyzer(history=("fix bug", "fix typo", "fix error"))
        chains = a.workflow_chains()
        self.assertEqual(len(chains), 1)
        self.assertEqual(len(chains[0]), 3)

    def test_multiple_chains(self):
        a = HistoryAnalyzer(history=("fix a", "fix b", "test x", "test y"))
        chains = a.workflow_chains()
        self.assertEqual(len(chains), 2)

    def test_returns_tuple_of_tuples(self):
        a = HistoryAnalyzer(history=("fix a", "fix b"))
        chains = a.workflow_chains()
        self.assertIsInstance(chains, tuple)
        self.assertIsInstance(chains[0], tuple)


if __name__ == "__main__":
    unittest.main()
