"""Tests for budget.efficiency."""
from __future__ import annotations

import unittest

from lidco.budget.efficiency import EfficiencyScore, EfficiencyScorer


class TestEfficiencyScore(unittest.TestCase):
    def test_frozen(self) -> None:
        es = EfficiencyScore()
        with self.assertRaises(AttributeError):
            es.score = 1.0  # type: ignore[misc]

    def test_defaults(self) -> None:
        es = EfficiencyScore()
        self.assertEqual(es.score, 0.0)
        self.assertEqual(es.useful_tokens, 0)
        self.assertEqual(es.total_tokens, 0)
        self.assertEqual(es.waste_tokens, 0)
        self.assertEqual(es.waste_patterns, ())
        self.assertEqual(es.grade, "C")


class TestEfficiencyScorer(unittest.TestCase):
    def setUp(self) -> None:
        self.scorer = EfficiencyScorer()

    def test_score_zero_total(self) -> None:
        result = self.scorer.score(0)
        self.assertEqual(result.score, 0.0)
        self.assertEqual(result.grade, "F")

    def test_score_with_useful_tokens(self) -> None:
        result = self.scorer.score(1000, useful_tokens=900)
        self.assertAlmostEqual(result.score, 0.9)
        self.assertEqual(result.grade, "A")
        self.assertEqual(result.waste_tokens, 100)

    def test_score_estimated_useful(self) -> None:
        # useful_tokens=0 so estimated = total - waste - compaction
        result = self.scorer.score(1000, tool_waste=200, compaction_savings=300)
        self.assertEqual(result.useful_tokens, 500)
        self.assertAlmostEqual(result.score, 0.5)
        self.assertEqual(result.grade, "C")

    def test_grade_b(self) -> None:
        result = self.scorer.score(1000, useful_tokens=700)
        self.assertEqual(result.grade, "B")

    def test_grade_d(self) -> None:
        result = self.scorer.score(1000, useful_tokens=250)
        self.assertEqual(result.grade, "D")

    def test_grade_f(self) -> None:
        result = self.scorer.score(1000, useful_tokens=100)
        self.assertEqual(result.grade, "F")

    def test_waste_pattern_excessive_tools(self) -> None:
        result = self.scorer.score(1000, useful_tokens=500, tool_waste=400)
        self.assertIn("excessive tool calls", result.waste_patterns)

    def test_waste_pattern_insufficient_compaction(self) -> None:
        result = self.scorer.score(1000, useful_tokens=800, compaction_savings=50)
        self.assertIn("insufficient compaction", result.waste_patterns)

    def test_no_waste_patterns(self) -> None:
        result = self.scorer.score(1000, useful_tokens=800, compaction_savings=200, tool_waste=100)
        self.assertEqual(result.waste_patterns, ())

    def test_rank(self) -> None:
        s1 = self.scorer.score(1000, useful_tokens=500)
        s2 = self.scorer.score(1000, useful_tokens=900)
        ranked = self.scorer.rank([s1, s2])
        self.assertEqual(ranked[0].score, s2.score)
        self.assertEqual(ranked[1].score, s1.score)

    def test_identify_waste(self) -> None:
        tools = {"read_file": 300, "search": 50, "write_file": 250}
        flagged = self.scorer.identify_waste(tools, 1000)
        # read_file=30% and write_file=25% should be flagged
        self.assertEqual(len(flagged), 2)
        self.assertTrue(any("read_file" in f for f in flagged))
        self.assertTrue(any("write_file" in f for f in flagged))

    def test_identify_waste_empty(self) -> None:
        self.assertEqual(self.scorer.identify_waste({}, 1000), [])

    def test_identify_waste_zero_total(self) -> None:
        self.assertEqual(self.scorer.identify_waste({"a": 100}, 0), [])

    def test_summary(self) -> None:
        result = self.scorer.score(1000, useful_tokens=900)
        s = self.scorer.summary(result)
        self.assertIn("Grade: A", s)
        self.assertIn("900/1000", s)

    def test_summary_with_patterns(self) -> None:
        result = self.scorer.score(1000, useful_tokens=500, tool_waste=400)
        s = self.scorer.summary(result)
        self.assertIn("Patterns:", s)


if __name__ == "__main__":
    unittest.main()
