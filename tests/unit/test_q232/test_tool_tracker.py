"""Tests for budget.tool_tracker — ToolTokenTracker."""
from __future__ import annotations

import unittest

from lidco.budget.tool_tracker import ToolTokenTracker, ToolUsage


class TestToolUsage(unittest.TestCase):
    def test_frozen(self):
        u = ToolUsage(tool_name="Read")
        with self.assertRaises(AttributeError):
            u.calls = 5  # type: ignore[misc]

    def test_defaults(self):
        u = ToolUsage(tool_name="x")
        self.assertEqual(u.calls, 0)
        self.assertEqual(u.total_tokens, 0)


class TestToolTokenTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = ToolTokenTracker()

    def test_record_and_get(self):
        self.tracker.record("Read", input_tokens=100, output_tokens=200)
        usage = self.tracker.get_usage("Read")
        self.assertIsNotNone(usage)
        self.assertEqual(usage.calls, 1)
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 200)
        self.assertEqual(usage.total_tokens, 300)

    def test_accumulates(self):
        self.tracker.record("Grep", input_tokens=50, output_tokens=100)
        self.tracker.record("Grep", input_tokens=50, output_tokens=100)
        usage = self.tracker.get_usage("Grep")
        self.assertEqual(usage.calls, 2)
        self.assertEqual(usage.total_tokens, 300)

    def test_get_unknown_returns_none(self):
        self.assertIsNone(self.tracker.get_usage("Nope"))

    def test_get_all_sorted(self):
        self.tracker.record("A", input_tokens=10, output_tokens=0)
        self.tracker.record("B", input_tokens=100, output_tokens=0)
        self.tracker.record("C", input_tokens=50, output_tokens=0)
        all_u = self.tracker.get_all()
        self.assertEqual([u.tool_name for u in all_u], ["B", "C", "A"])

    def test_hottest(self):
        for i in range(10):
            self.tracker.record(f"tool_{i}", input_tokens=(i + 1) * 100)
        hot = self.tracker.hottest(3)
        self.assertEqual(len(hot), 3)
        self.assertEqual(hot[0].tool_name, "tool_9")

    def test_total_tokens(self):
        self.tracker.record("A", input_tokens=100, output_tokens=50)
        self.tracker.record("B", input_tokens=200, output_tokens=100)
        self.assertEqual(self.tracker.total_tokens(), 450)

    def test_reset(self):
        self.tracker.record("X", input_tokens=500)
        self.tracker.reset()
        self.assertEqual(self.tracker.total_tokens(), 0)
        self.assertEqual(self.tracker.get_all(), [])

    def test_summary_empty(self):
        self.assertEqual(self.tracker.summary(), "No tool usage recorded.")

    def test_summary_with_data(self):
        self.tracker.record("Read", input_tokens=1000, output_tokens=500)
        s = self.tracker.summary()
        self.assertIn("Read", s)
        self.assertIn("1 calls", s)
        self.assertIn("1,500", s)


if __name__ == "__main__":
    unittest.main()
