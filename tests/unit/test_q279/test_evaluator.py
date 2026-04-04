"""Tests for debate.evaluator."""
import unittest
from lidco.debate.evaluator import ArgumentEvaluator, ArgumentScore


class TestArgumentEvaluator(unittest.TestCase):

    def setUp(self):
        self.ev = ArgumentEvaluator()

    def test_evaluate_basic(self):
        score = self.ev.evaluate("agent1", "This is a good approach because it simplifies things.")
        self.assertIsInstance(score, ArgumentScore)
        self.assertGreaterEqual(score.overall, 0.0)
        self.assertLessEqual(score.overall, 1.0)

    def test_evidence_boosts_score(self):
        s1 = self.ev.evaluate("a", "No evidence argument")
        s2 = self.ev.evaluate("b", "With evidence", evidence=["ref1", "ref2", "ref3", "ref4"])
        self.assertGreater(s2.evidence_quality, s1.evidence_quality)

    def test_logic_indicators(self):
        s = self.ev.evaluate("a", "We should do this because it is fast, therefore optimal, however we need to check since given that thus")
        self.assertGreater(s.logical_consistency, 0.0)

    def test_novelty_decreases_with_repetition(self):
        s1 = self.ev.evaluate("a", "Unique fresh argument about databases")
        s2 = self.ev.evaluate("b", "Unique fresh argument about databases", prior_arguments=["Unique fresh argument about databases"])
        self.assertGreater(s1.novelty, s2.novelty)

    def test_agent_scores(self):
        self.ev.evaluate("agent1", "First")
        self.ev.evaluate("agent1", "Second")
        self.ev.evaluate("agent2", "Third")
        self.assertEqual(len(self.ev.agent_scores("agent1")), 2)
        self.assertEqual(len(self.ev.agent_scores("agent2")), 1)

    def test_leaderboard(self):
        self.ev.evaluate("a", "Short")
        self.ev.evaluate("b", "Much longer argument with evidence because therefore", evidence=["e1", "e2"])
        lb = self.ev.leaderboard()
        self.assertEqual(len(lb), 2)
        # b should score higher
        self.assertEqual(lb[0][0], "b")

    def test_custom_weights(self):
        ev = ArgumentEvaluator(weights={"evidence_quality": 1.0, "logical_consistency": 0.0, "novelty": 0.0, "persuasiveness": 0.0})
        s = ev.evaluate("a", "No evidence")
        self.assertEqual(s.overall, 0.0)

    def test_feedback_generated(self):
        s = self.ev.evaluate("a", "Short")
        self.assertIn("evidence", s.feedback.lower())

    def test_weights_property(self):
        w = self.ev.weights
        self.assertIn("evidence_quality", w)


if __name__ == "__main__":
    unittest.main()
