"""Tests for lidco.profiler.memory."""
from __future__ import annotations

import unittest

from lidco.profiler.memory import MemoryProfiler, MemorySnapshot


class TestMemorySnapshot(unittest.TestCase):
    def test_defaults(self):
        s = MemorySnapshot(timestamp=1.0, total_bytes=0)
        self.assertEqual(s.total_bytes, 0)
        self.assertEqual(s.allocations, {})
        self.assertEqual(s.peak_bytes, 0)


class TestMemoryProfiler(unittest.TestCase):
    def setUp(self):
        self.mp = MemoryProfiler()

    def test_snapshot_empty(self):
        snap = self.mp.snapshot()
        self.assertEqual(snap.total_bytes, 0)
        self.assertEqual(snap.peak_bytes, 0)

    def test_record_allocation(self):
        self.mp.record_allocation("module_a", 1024)
        snap = self.mp.snapshot()
        self.assertEqual(snap.total_bytes, 1024)
        self.assertIn("module_a", snap.allocations)

    def test_record_deallocation(self):
        self.mp.record_allocation("mod", 2048)
        self.mp.record_deallocation("mod", 1024)
        snap = self.mp.snapshot()
        self.assertEqual(snap.total_bytes, 1024)

    def test_deallocation_floor_zero(self):
        self.mp.record_allocation("mod", 100)
        self.mp.record_deallocation("mod", 500)
        snap = self.mp.snapshot()
        self.assertEqual(snap.total_bytes, 0)

    def test_peak_tracking(self):
        self.mp.record_allocation("a", 5000)
        self.mp.record_deallocation("a", 4000)
        snap = self.mp.snapshot()
        self.assertEqual(snap.peak_bytes, 5000)

    def test_detect_leaks(self):
        self.mp.record_allocation("leaky", 500)
        self.mp.record_allocation("leaky", 600)  # grows to 1100
        leaks = self.mp.detect_leaks(threshold_bytes=1000)
        self.assertEqual(len(leaks), 1)
        self.assertEqual(leaks[0]["source"], "leaky")

    def test_detect_no_leaks(self):
        self.mp.record_allocation("ok", 100)
        leaks = self.mp.detect_leaks(threshold_bytes=1000)
        self.assertEqual(len(leaks), 0)

    def test_top_allocators(self):
        self.mp.record_allocation("big", 5000)
        self.mp.record_allocation("small", 100)
        self.mp.record_allocation("medium", 2000)
        top = self.mp.top_allocators(limit=2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0][0], "big")

    def test_snapshots_list(self):
        self.mp.snapshot("s1")
        self.mp.snapshot("s2")
        self.assertEqual(len(self.mp.snapshots()), 2)

    def test_growth_trend(self):
        self.mp.record_allocation("a", 100)
        self.mp.snapshot()
        self.mp.record_allocation("a", 200)
        self.mp.snapshot()
        trend = self.mp.growth_trend()
        self.assertEqual(len(trend), 2)
        self.assertLess(trend[0]["total_bytes"], trend[1]["total_bytes"])

    def test_summary(self):
        self.mp.record_allocation("x", 1024)
        s = self.mp.summary()
        self.assertEqual(s["active_sources"], 1)
        self.assertEqual(s["total_bytes"], 1024)


if __name__ == "__main__":
    unittest.main()
