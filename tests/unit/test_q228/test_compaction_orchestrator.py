"""Tests for budget.compaction_orchestrator."""
from __future__ import annotations

import unittest

from lidco.budget.compaction_orchestrator import (
    CompactionEvent,
    CompactionOrchestrator,
    CompactionTrigger,
)


class TestCompactionTrigger(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(CompactionTrigger.THRESHOLD, "threshold")
        self.assertEqual(CompactionTrigger.EMERGENCY, "emergency")


class TestCompactionEvent(unittest.TestCase):
    def test_frozen(self):
        ev = CompactionEvent(trigger=CompactionTrigger.MANUAL, before_tokens=100)
        with self.assertRaises(AttributeError):
            ev.before_tokens = 50  # type: ignore[misc]

    def test_defaults(self):
        ev = CompactionEvent(trigger=CompactionTrigger.MANUAL)
        self.assertEqual(ev.before_tokens, 0)
        self.assertEqual(ev.strategy, "")
        self.assertGreater(ev.timestamp, 0)


class TestCompactionOrchestrator(unittest.TestCase):
    def setUp(self):
        self.orch = CompactionOrchestrator()

    def test_no_compact_below_warn(self):
        self.assertIsNone(self.orch.should_compact(0.5))

    def test_threshold_at_warn(self):
        self.assertEqual(self.orch.should_compact(0.72), CompactionTrigger.THRESHOLD)

    def test_pre_call_at_critical(self):
        self.assertEqual(self.orch.should_compact(0.88), CompactionTrigger.PRE_CALL)

    def test_emergency_at_high(self):
        self.assertEqual(self.orch.should_compact(0.96), CompactionTrigger.EMERGENCY)

    def test_disabled_returns_none(self):
        self.orch.disable()
        self.assertIsNone(self.orch.should_compact(0.99))
        self.assertFalse(self.orch.is_enabled())

    def test_enable_after_disable(self):
        self.orch.disable()
        self.orch.enable()
        self.assertTrue(self.orch.is_enabled())
        self.assertIsNotNone(self.orch.should_compact(0.96))

    def test_select_strategy_low(self):
        self.assertEqual(self.orch.select_strategy(0.75), "trim_old_tool_results")

    def test_select_strategy_mid(self):
        self.assertEqual(self.orch.select_strategy(0.90), "summarize_middle")

    def test_select_strategy_high(self):
        self.assertEqual(self.orch.select_strategy(0.96), "aggressive_prune")

    def test_record_and_get_events(self):
        ev = self.orch.record_compaction(
            CompactionTrigger.THRESHOLD, before=1000, after=600,
            strategy="trim", messages_affected=5,
        )
        self.assertEqual(ev.before_tokens, 1000)
        self.assertEqual(len(self.orch.get_events()), 1)

    def test_total_saved(self):
        self.orch.record_compaction(CompactionTrigger.MANUAL, 1000, 600, "a")
        self.orch.record_compaction(CompactionTrigger.MANUAL, 500, 200, "b")
        self.assertEqual(self.orch.total_saved(), 700)

    def test_summary_empty(self):
        self.assertIn("no events", self.orch.summary())

    def test_summary_with_events(self):
        self.orch.record_compaction(CompactionTrigger.MANUAL, 100, 50, "x")
        s = self.orch.summary()
        self.assertIn("1 events", s)
        self.assertIn("50 tokens saved", s)


if __name__ == "__main__":
    unittest.main()
