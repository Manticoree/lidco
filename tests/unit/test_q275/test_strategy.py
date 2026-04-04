"""Tests for lidco.recovery.strategy."""
from __future__ import annotations

import unittest

from lidco.recovery.strategy import RecoveryAction, RecoveryChain, RecoveryStrategy


class TestRecoveryAction(unittest.TestCase):
    def test_defaults(self):
        a = RecoveryAction(type="retry", description="try again")
        self.assertEqual(a.max_attempts, 3)
        self.assertEqual(a.backoff_seconds, 1.0)

    def test_frozen(self):
        a = RecoveryAction(type="retry", description="x")
        with self.assertRaises(AttributeError):
            a.type = "skip"  # type: ignore[misc]


class TestRecoveryStrategy(unittest.TestCase):
    def setUp(self):
        self.strat = RecoveryStrategy()

    def test_get_chain_known(self):
        chain = self.strat.get_chain("syntax")
        self.assertEqual(chain.error_type, "syntax")
        self.assertTrue(len(chain.actions) > 0)

    def test_get_chain_unknown_fallback(self):
        chain = self.strat.get_chain("nonexistent")
        self.assertEqual(chain.error_type, "unknown")

    def test_add_chain(self):
        custom = RecoveryChain("custom", [RecoveryAction("skip", "just skip")])
        result = self.strat.add_chain(custom)
        self.assertIs(result, custom)
        self.assertEqual(self.strat.get_chain("custom").error_type, "custom")

    def test_next_action_first(self):
        action = self.strat.next_action("network", 0)
        self.assertIsNotNone(action)
        self.assertEqual(action.type, "retry")

    def test_next_action_exhausted(self):
        action = self.strat.next_action("syntax", 100)
        self.assertIsNone(action)

    def test_next_action_negative(self):
        action = self.strat.next_action("syntax", -1)
        self.assertIsNone(action)

    def test_next_action_second_phase(self):
        # syntax: first action has max_attempts=2, second is escalate
        action = self.strat.next_action("syntax", 2)
        self.assertIsNotNone(action)
        self.assertEqual(action.type, "escalate")

    def test_all_chains(self):
        chains = self.strat.all_chains()
        self.assertGreater(len(chains), 0)
        types = {c.error_type for c in chains}
        self.assertIn("syntax", types)
        self.assertIn("network", types)

    def test_summary(self):
        s = self.strat.summary()
        self.assertIn("chain_count", s)
        self.assertIn("total_actions", s)
        self.assertGreater(s["chain_count"], 0)

    def test_all_default_types(self):
        for t in ["syntax", "runtime", "network", "permission", "resource", "timeout", "unknown"]:
            chain = self.strat.get_chain(t)
            self.assertEqual(chain.error_type, t)


if __name__ == "__main__":
    unittest.main()
