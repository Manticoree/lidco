"""Tests for hallucination.consistency."""
import unittest
from lidco.hallucination.consistency import ConsistencyChecker, Contradiction


class TestConsistencyChecker(unittest.TestCase):

    def setUp(self):
        self.cc = ConsistencyChecker()

    def test_consistent_statements(self):
        result = self.cc.check(["Python is fast", "Python has good libraries"])
        self.assertTrue(result.is_consistent)
        self.assertEqual(len(result.contradictions), 0)

    def test_contradicting_statements(self):
        result = self.cc.check([
            "This function is deprecated",
            "This function is recommended for use",
        ])
        self.assertGreater(len(result.contradictions), 0)

    def test_negation_detection(self):
        result = self.cc.check([
            "The API does support pagination",
            "The API does not support pagination",
        ])
        self.assertFalse(result.is_consistent)

    def test_prior_statement_contradiction(self):
        self.cc.add_prior("Python is not suitable for this task")
        result = self.cc.check(["Python is suitable for this task"])
        contradictions = [c for c in result.contradictions if c.severity == "high"]
        self.assertGreater(len(contradictions), 0)

    def test_no_prior_no_cross_check(self):
        result = self.cc.check(["Single statement"])
        self.assertTrue(result.is_consistent)

    def test_confidence_decreases_with_contradictions(self):
        r1 = self.cc.check(["A is true"])
        r2 = self.cc.check([
            "This is not possible",
            "This is possible",
        ])
        self.assertGreaterEqual(r1.confidence, r2.confidence)

    def test_history(self):
        self.cc.check(["A"])
        self.cc.check(["B"])
        self.assertEqual(len(self.cc.history()), 2)

    def test_summary(self):
        self.cc.add_prior("Prior")
        s = self.cc.summary()
        self.assertEqual(s["prior_statements"], 1)

    def test_empty_check(self):
        result = self.cc.check([])
        self.assertTrue(result.is_consistent)


if __name__ == "__main__":
    unittest.main()
