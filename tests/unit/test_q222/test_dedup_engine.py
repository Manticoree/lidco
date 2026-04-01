"""Tests for lidco.tools.dedup_engine."""
from __future__ import annotations

import unittest

from lidco.tools.dedup_engine import DedupEngine, DedupRecord


class TestDedupRecord(unittest.TestCase):
    def test_frozen(self) -> None:
        rec = DedupRecord(tool_name="t", args="a")
        with self.assertRaises(AttributeError):
            rec.tool_name = "x"  # type: ignore[misc]

    def test_defaults(self) -> None:
        rec = DedupRecord(tool_name="t", args="a")
        self.assertEqual(rec.call_count, 1)
        self.assertEqual(rec.last_result, "")


class TestDedupEngine(unittest.TestCase):
    def test_check_returns_none_on_first_call(self) -> None:
        engine = DedupEngine()
        self.assertIsNone(engine.check("grep", "pattern"))

    def test_record_and_check(self) -> None:
        engine = DedupEngine()
        engine.record("grep", "pattern", "found")
        result = engine.check("grep", "pattern")
        self.assertEqual(result, "found")

    def test_call_count_increments_on_check(self) -> None:
        engine = DedupEngine()
        engine.record("grep", "p", "r")
        engine.check("grep", "p")
        engine.check("grep", "p")
        dups = engine.get_duplicates()
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0].call_count, 3)

    def test_get_duplicates_only_multi(self) -> None:
        engine = DedupEngine()
        engine.record("grep", "a", "r1")
        engine.record("read", "b", "r2")
        engine.check("grep", "a")
        dups = engine.get_duplicates()
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0].tool_name, "grep")

    def test_savings(self) -> None:
        engine = DedupEngine()
        engine.record("t", "a", "r")
        engine.check("t", "a")
        engine.record("t2", "b", "r2")
        s = engine.savings()
        self.assertEqual(s["total_calls"], 3)
        self.assertEqual(s["unique_calls"], 2)
        self.assertEqual(s["deduped_calls"], 1)
        self.assertEqual(s["saved_tokens"], 50)

    def test_clear(self) -> None:
        engine = DedupEngine()
        engine.record("t", "a", "r")
        engine.clear()
        self.assertEqual(engine.savings()["total_calls"], 0)

    def test_summary(self) -> None:
        engine = DedupEngine()
        engine.record("t", "a", "r")
        s = engine.summary()
        self.assertIn("DedupEngine", s)
        self.assertIn("1 unique", s)

    def test_record_updates_existing(self) -> None:
        engine = DedupEngine()
        engine.record("t", "a", "r1")
        rec = engine.record("t", "a", "r2")
        self.assertEqual(rec.call_count, 2)
        self.assertEqual(rec.last_result, "r2")

    def test_different_args_separate_records(self) -> None:
        engine = DedupEngine()
        engine.record("t", "a", "r1")
        engine.record("t", "b", "r2")
        self.assertEqual(engine.savings()["unique_calls"], 2)

    def test_check_does_not_create_record(self) -> None:
        engine = DedupEngine()
        engine.check("t", "a")
        self.assertEqual(engine.savings()["total_calls"], 0)


if __name__ == "__main__":
    unittest.main()
