"""Tests for ToolUseAnalyzer."""
from __future__ import annotations

import unittest

from lidco.tool_opt.analyzer import CallRecord, ToolUseAnalyzer


class TestCallRecord(unittest.TestCase):
    def test_fields(self):
        r = CallRecord(tool_name="Read", args={"path": "f.py"}, duration=0.1)
        self.assertEqual(r.tool_name, "Read")
        self.assertEqual(r.args, {"path": "f.py"})
        self.assertAlmostEqual(r.duration, 0.1)
        self.assertGreater(r.timestamp, 0)


class TestToolUseAnalyzer(unittest.TestCase):
    def setUp(self):
        self.a = ToolUseAnalyzer()

    def test_record_call(self):
        rec = self.a.record_call("Read", {"path": "a.py"}, 0.5)
        self.assertEqual(rec.tool_name, "Read")
        self.assertEqual(len(self.a.calls), 1)

    def test_record_call_defaults(self):
        rec = self.a.record_call("Edit")
        self.assertEqual(rec.args, {})
        self.assertEqual(rec.duration, 0.0)

    def test_efficiency_score_empty(self):
        self.assertEqual(self.a.efficiency_score(), 1.0)

    def test_efficiency_score_with_duplicates(self):
        self.a.record_call("Read", {"path": "a.py"}, 0.0)
        self.a.record_call("Read", {"path": "a.py"}, 0.0)
        score = self.a.efficiency_score()
        self.assertLess(score, 1.0)

    def test_efficiency_score_no_duplicates(self):
        self.a.record_call("Read", {"path": "a.py"}, 0.0)
        self.a.record_call("Read", {"path": "b.py"}, 0.0)
        score = self.a.efficiency_score()
        self.assertEqual(score, 1.0)

    def test_unnecessary_calls_empty(self):
        self.assertEqual(self.a.unnecessary_calls(), [])

    def test_unnecessary_calls_detected(self):
        self.a.record_call("Read", {"path": "a.py"})
        self.a.record_call("Read", {"path": "a.py"})
        self.a.record_call("Edit", {"path": "a.py"})
        dupes = self.a.unnecessary_calls()
        self.assertEqual(len(dupes), 1)
        self.assertEqual(dupes[0].tool_name, "Read")

    def test_missed_opportunities_read_batching(self):
        for i in range(4):
            self.a.record_call("Read", {"path": f"f{i}.py"})
        hints = self.a.missed_opportunities()
        self.assertTrue(any("batching" in h for h in hints))

    def test_missed_opportunities_edit_read_edit(self):
        self.a.record_call("Edit", {"path": "a.py"})
        self.a.record_call("Read", {"path": "a.py"})
        self.a.record_call("Edit", {"path": "a.py"})
        hints = self.a.missed_opportunities()
        self.assertTrue(any("Edit-Read-Edit" in h for h in hints))

    def test_missed_opportunities_none(self):
        self.a.record_call("Edit", {"path": "a.py"})
        self.assertEqual(self.a.missed_opportunities(), [])

    def test_summary_keys(self):
        self.a.record_call("Read", {"path": "a.py"}, 0.1)
        s = self.a.summary()
        self.assertEqual(s["total_calls"], 1)
        self.assertIn("tool_counts", s)
        self.assertIn("efficiency_score", s)
        self.assertIn("unnecessary_calls", s)
        self.assertIn("missed_opportunities", s)
        self.assertAlmostEqual(s["total_duration"], 0.1, places=3)

    def test_summary_tool_counts(self):
        self.a.record_call("Read")
        self.a.record_call("Read")
        self.a.record_call("Edit")
        s = self.a.summary()
        self.assertEqual(s["tool_counts"]["Read"], 2)
        self.assertEqual(s["tool_counts"]["Edit"], 1)


if __name__ == "__main__":
    unittest.main()
