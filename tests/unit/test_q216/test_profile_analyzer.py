"""Tests for perf_intel.profile_analyzer."""
from __future__ import annotations

import unittest

from lidco.perf_intel.profile_analyzer import (
    ProfileAnalyzer,
    ProfileEntry,
    ProfileReport,
)


class TestProfileEntry(unittest.TestCase):
    def test_frozen(self):
        e = ProfileEntry(function="foo")
        with self.assertRaises(AttributeError):
            e.function = "bar"  # type: ignore[misc]

    def test_defaults(self):
        e = ProfileEntry(function="f")
        self.assertEqual(e.file, "")
        self.assertEqual(e.calls, 0)
        self.assertAlmostEqual(e.total_time, 0.0)


class TestProfileAnalyzer(unittest.TestCase):
    def _make_entries(self) -> list[ProfileEntry]:
        return [
            ProfileEntry("a", calls=10, total_time=1.0, cumulative_time=2.0, per_call=0.2),
            ProfileEntry("b", calls=5, total_time=3.0, cumulative_time=5.0, per_call=1.0),
            ProfileEntry("c", calls=20, total_time=0.5, cumulative_time=0.5, per_call=0.025),
        ]

    def test_add_entry_and_report(self):
        analyzer = ProfileAnalyzer()
        for e in self._make_entries():
            analyzer.add_entry(e)
        r = analyzer.report()
        self.assertEqual(r.entry_count, 3)
        self.assertAlmostEqual(r.total_time, 4.5)

    def test_top_functions(self):
        analyzer = ProfileAnalyzer()
        for e in self._make_entries():
            analyzer.add_entry(e)
        top = analyzer.top_functions(2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0].function, "b")
        self.assertEqual(top[1].function, "a")

    def test_hot_paths(self):
        analyzer = ProfileAnalyzer()
        for e in self._make_entries():
            analyzer.add_entry(e)
        hot = analyzer.hot_paths()
        # avg per_call = (0.2 + 1.0 + 0.025) / 3 ≈ 0.408
        funcs = {e.function for e in hot}
        self.assertIn("b", funcs)
        self.assertNotIn("c", funcs)

    def test_hot_paths_empty(self):
        analyzer = ProfileAnalyzer()
        self.assertEqual(analyzer.hot_paths(), [])

    def test_compare(self):
        analyzer = ProfileAnalyzer()
        r1 = ProfileReport(
            entries=(ProfileEntry("x", cumulative_time=1.0),),
            total_time=1.0, entry_count=1,
        )
        r2 = ProfileReport(
            entries=(ProfileEntry("x", cumulative_time=2.0), ProfileEntry("y", cumulative_time=0.5)),
            total_time=2.5, entry_count=2,
        )
        diff = analyzer.compare(r1, r2)
        self.assertEqual(diff["x"], (1.0, 2.0))
        self.assertEqual(diff["y"], (0.0, 0.5))

    def test_summary(self):
        analyzer = ProfileAnalyzer()
        analyzer.add_entry(ProfileEntry("run", calls=1, total_time=0.5, cumulative_time=0.5))
        s = analyzer.summary()
        self.assertIn("Profile:", s)
        self.assertIn("run", s)

    def test_report_is_frozen(self):
        r = ProfileReport()
        with self.assertRaises(AttributeError):
            r.total_time = 99.0  # type: ignore[misc]

    def test_top_functions_more_than_available(self):
        analyzer = ProfileAnalyzer()
        analyzer.add_entry(ProfileEntry("only", cumulative_time=1.0))
        top = analyzer.top_functions(10)
        self.assertEqual(len(top), 1)


if __name__ == "__main__":
    unittest.main()
