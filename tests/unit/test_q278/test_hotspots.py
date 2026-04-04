"""Tests for lidco.profiler.hotspots."""
from __future__ import annotations

import unittest

from lidco.profiler.hotspots import Hotspot, HotspotFinder
from lidco.profiler.runner import ProfileRunner


class TestHotspot(unittest.TestCase):
    def test_frozen(self):
        h = Hotspot(
            function_name="foo", file_path="a.py",
            time_ms=10.0, call_count=5, percentage=50.0,
        )
        with self.assertRaises(AttributeError):
            h.function_name = "bar"

    def test_default_suggestion(self):
        h = Hotspot(
            function_name="foo", file_path="a.py",
            time_ms=1.0, call_count=1, percentage=1.0,
        )
        self.assertEqual(h.suggestion, "")


class TestHotspotFinder(unittest.TestCase):
    def setUp(self):
        self.finder = HotspotFinder()
        self.runner = ProfileRunner()

    def test_find(self):
        result = self.runner.profile("foo()\nbar()\nbaz()")
        hotspots = self.finder.find(result, limit=2)
        self.assertLessEqual(len(hotspots), 2)
        for h in hotspots:
            self.assertIsInstance(h, Hotspot)

    def test_find_empty(self):
        from lidco.profiler.runner import ProfileResult
        result = ProfileResult(name="empty", total_time=0, call_count=0, entries=[])
        self.assertEqual(self.finder.find(result), [])

    def test_by_calls(self):
        result = self.runner.profile("foo()\nx = 1\nbar()")
        hotspots = self.finder.by_calls(result, limit=10)
        self.assertTrue(len(hotspots) > 0)
        # First item should have highest call count
        self.assertGreaterEqual(hotspots[0].call_count, hotspots[-1].call_count)

    def test_suggest_loop(self):
        h = Hotspot(
            function_name="for i in loop()", file_path="a.py",
            time_ms=10.0, call_count=1, percentage=10.0,
        )
        s = self.finder.suggest_optimization(h)
        self.assertIn("loop", s.lower())

    def test_suggest_sort(self):
        h = Hotspot(
            function_name="sorted(data)", file_path="a.py",
            time_ms=10.0, call_count=1, percentage=10.0,
        )
        s = self.finder.suggest_optimization(h)
        self.assertIn("sort", s.lower())

    def test_suggest_high_calls(self):
        h = Hotspot(
            function_name="something_generic", file_path="a.py",
            time_ms=1.0, call_count=200, percentage=1.0,
        )
        s = self.finder.suggest_optimization(h)
        self.assertIn("cach", s.lower())

    def test_suggest_fallback(self):
        h = Hotspot(
            function_name="unique_fn", file_path="a.py",
            time_ms=1.0, call_count=1, percentage=1.0,
        )
        s = self.finder.suggest_optimization(h)
        self.assertIn("algorithm", s.lower())

    def test_compare_hotspots(self):
        before = [
            Hotspot("fn_a", "a.py", 10.0, 5, 50.0),
            Hotspot("fn_b", "b.py", 5.0, 3, 25.0),
        ]
        after = [
            Hotspot("fn_a", "a.py", 7.0, 5, 35.0),
            Hotspot("fn_c", "c.py", 3.0, 2, 15.0),
        ]
        diffs = self.finder.compare_hotspots(before, after)
        names = [d["function"] for d in diffs]
        self.assertIn("fn_a", names)
        self.assertIn("fn_b", names)
        self.assertIn("fn_c", names)
        a_diff = next(d for d in diffs if d["function"] == "fn_a")
        self.assertEqual(a_diff["status"], "improved")
        b_diff = next(d for d in diffs if d["function"] == "fn_b")
        self.assertEqual(b_diff["status"], "removed")

    def test_summary(self):
        result = self.runner.profile("x = 1\ny = 2")
        s = self.finder.summary(result)
        self.assertIn("total_hotspots", s)
        self.assertIn("top5", s)


if __name__ == "__main__":
    unittest.main()
