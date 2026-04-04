"""Tests for debate.consensus."""
import unittest
from lidco.debate.consensus import ConsensusBuilder, ConsensusResult


class TestConsensusBuilder(unittest.TestCase):

    def setUp(self):
        self.cb = ConsensusBuilder()

    def test_majority_vote(self):
        self.cb.cast_vote("a", "approve")
        self.cb.cast_vote("b", "approve")
        self.cb.cast_vote("c", "reject")
        pos, pct = self.cb.majority_vote()
        self.assertEqual(pos, "approve")
        self.assertAlmostEqual(pct, 0.667, places=2)

    def test_empty_vote(self):
        pos, pct = self.cb.majority_vote()
        self.assertEqual(pos, "none")
        self.assertEqual(pct, 0.0)

    def test_weighted_vote(self):
        self.cb.set_expertise_weight("a", 0.9)
        self.cb.set_expertise_weight("b", 0.1)
        self.cb.cast_vote("a", "approve")
        self.cb.cast_vote("b", "reject")
        pos, score = self.cb.weighted_vote()
        self.assertEqual(pos, "approve")
        self.assertGreater(score, 0.5)

    def test_add_dissent(self):
        self.cb.add_dissent("I disagree because of X")
        s = self.cb.summary()
        self.assertEqual(s["dissents"], 1)

    def test_build_result(self):
        self.cb.add_position("a", ["Point 1", "Point 2"])
        self.cb.add_position("b", ["Counter 1"])
        self.cb.cast_vote("a", "approve")
        self.cb.cast_vote("b", "reject")
        result = self.cb.build("Final decision")
        self.assertIsInstance(result, ConsensusResult)
        self.assertEqual(result.decision, "Final decision")
        self.assertGreater(result.confidence, 0.0)

    def test_build_default_decision(self):
        self.cb.cast_vote("a", "approve")
        result = self.cb.build()
        self.assertIn("approve", result.decision)

    def test_supporting_and_dissenting(self):
        self.cb.add_position("a", ["Good point"])
        self.cb.add_position("b", ["Bad point"])
        self.cb.cast_vote("a", "approve")
        self.cb.cast_vote("b", "reject")
        result = self.cb.build()
        self.assertIn("Good point", result.supporting_points)
        self.assertIn("Bad point", result.dissenting_points)

    def test_abstentions(self):
        self.cb.add_position("a", ["Arg"])
        self.cb.add_position("b", ["Arg"])
        self.cb.cast_vote("a", "approve")
        result = self.cb.build()
        self.assertEqual(result.abstentions, 1)

    def test_summary(self):
        self.cb.add_position("a", ["P1"])
        self.cb.cast_vote("a", "approve")
        s = self.cb.summary()
        self.assertEqual(s["positions"], 1)
        self.assertEqual(s["votes"], 1)

    def test_expertise_weight_clamped(self):
        self.cb.set_expertise_weight("a", 5.0)
        self.cb.set_expertise_weight("b", -1.0)
        self.cb.cast_vote("a", "y")
        self.cb.cast_vote("b", "n")
        pos, score = self.cb.weighted_vote()
        # Weight should be clamped to [0, 1]
        self.assertEqual(pos, "y")


if __name__ == "__main__":
    unittest.main()
