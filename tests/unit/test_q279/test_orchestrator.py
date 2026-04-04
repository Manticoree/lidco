"""Tests for debate.orchestrator."""
import unittest
from lidco.debate.orchestrator import (
    DebateOrchestrator, DebateConfig, DebateRole, Argument,
)


class TestDebateOrchestrator(unittest.TestCase):

    def setUp(self):
        self.config = DebateConfig(topic="Use microservices?", rounds=3)
        self.orch = DebateOrchestrator(self.config)

    def test_add_participant(self):
        self.orch.add_participant("agent1", DebateRole.PROPOSITION)
        self.assertIn("agent1", self.orch.participants())

    def test_cannot_add_after_start(self):
        self.orch.add_participant("a", DebateRole.PROPOSITION)
        self.orch.add_participant("b", DebateRole.OPPOSITION)
        self.orch.start()
        with self.assertRaises(RuntimeError):
            self.orch.add_participant("c", DebateRole.JUDGE)

    def test_start_requires_topic(self):
        orch = DebateOrchestrator(DebateConfig(topic=""))
        orch.add_participant("a", DebateRole.PROPOSITION)
        orch.add_participant("b", DebateRole.OPPOSITION)
        with self.assertRaises(ValueError):
            orch.start()

    def test_start_requires_both_sides(self):
        self.orch.add_participant("a", DebateRole.PROPOSITION)
        with self.assertRaises(ValueError):
            self.orch.start()

    def test_submit_argument(self):
        self.orch.add_participant("a", DebateRole.PROPOSITION)
        self.orch.add_participant("b", DebateRole.OPPOSITION)
        self.orch.start()
        arg = self.orch.submit_argument("a", "Microservices scale better")
        self.assertIsInstance(arg, Argument)
        self.assertEqual(arg.role, DebateRole.PROPOSITION)

    def test_judge_cannot_argue(self):
        self.orch.add_participant("a", DebateRole.PROPOSITION)
        self.orch.add_participant("b", DebateRole.OPPOSITION)
        self.orch.add_participant("j", DebateRole.JUDGE)
        self.orch.start()
        with self.assertRaises(ValueError):
            self.orch.submit_argument("j", "I think...")

    def test_advance_round(self):
        self.orch.add_participant("a", DebateRole.PROPOSITION)
        self.orch.add_participant("b", DebateRole.OPPOSITION)
        self.orch.start()
        self.assertEqual(self.orch.current_round, 1)
        self.orch.advance_round()
        self.assertEqual(self.orch.current_round, 2)

    def test_finish_after_max_rounds(self):
        self.orch.add_participant("a", DebateRole.PROPOSITION)
        self.orch.add_participant("b", DebateRole.OPPOSITION)
        self.orch.start()
        for _ in range(3):
            self.orch.advance_round()
        self.assertTrue(self.orch.is_finished)

    def test_voting_and_tally(self):
        self.orch.add_participant("a", DebateRole.PROPOSITION)
        self.orch.add_participant("b", DebateRole.OPPOSITION)
        self.orch.start()
        self.orch.cast_vote("voter1", "a")
        self.orch.cast_vote("voter2", "a")
        self.orch.cast_vote("voter3", "b")
        tally = self.orch.tally_votes()
        self.assertEqual(tally["a"], 2)
        self.assertEqual(tally["b"], 1)

    def test_finish_result(self):
        self.orch.add_participant("a", DebateRole.PROPOSITION)
        self.orch.add_participant("b", DebateRole.OPPOSITION)
        self.orch.start()
        self.orch.submit_argument("a", "Pro argument")
        self.orch.cast_vote("v1", "a")
        result = self.orch.finish()
        self.assertEqual(result.topic, "Use microservices?")
        self.assertEqual(result.winner, "a")
        self.assertEqual(len(result.arguments), 1)

    def test_require_evidence(self):
        cfg = DebateConfig(topic="Test", require_evidence=True)
        orch = DebateOrchestrator(cfg)
        orch.add_participant("a", DebateRole.PROPOSITION)
        orch.add_participant("b", DebateRole.OPPOSITION)
        orch.start()
        with self.assertRaises(ValueError):
            orch.submit_argument("a", "No evidence here")

    def test_arguments_for_round(self):
        self.orch.add_participant("a", DebateRole.PROPOSITION)
        self.orch.add_participant("b", DebateRole.OPPOSITION)
        self.orch.start()
        self.orch.submit_argument("a", "Round 1 arg")
        self.orch.advance_round()
        self.orch.submit_argument("b", "Round 2 arg")
        r1 = self.orch.arguments_for_round(1)
        r2 = self.orch.arguments_for_round(2)
        self.assertEqual(len(r1), 1)
        self.assertEqual(len(r2), 1)

    def test_summary(self):
        s = self.orch.summary()
        self.assertEqual(s["topic"], "Use microservices?")
        self.assertFalse(s["started"])


if __name__ == "__main__":
    unittest.main()
