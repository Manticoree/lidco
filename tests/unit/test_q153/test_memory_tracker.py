"""Tests for MemoryTracker."""
from __future__ import annotations

import unittest

from lidco.perf.memory_tracker import MemoryTracker, MemorySnapshot, _fmt_bytes


class TestMemorySnapshot(unittest.TestCase):
    def test_fields(self):
        s = MemorySnapshot(label="init", timestamp=1.0, rss_bytes=1024, delta_bytes=0)
        self.assertEqual(s.label, "init")
        self.assertEqual(s.rss_bytes, 1024)

    def test_delta(self):
        s = MemorySnapshot(label="x", timestamp=0, rss_bytes=2048, delta_bytes=1024)
        self.assertEqual(s.delta_bytes, 1024)


class TestMemoryTrackerInit(unittest.TestCase):
    def test_default_fn(self):
        t = MemoryTracker()
        self.assertIsNotNone(t._get_memory)

    def test_custom_fn(self):
        calls = []
        def mem_fn():
            calls.append(1)
            return 5000
        t = MemoryTracker(get_memory_fn=mem_fn)
        t.snapshot("test")
        self.assertTrue(len(calls) > 0)


class TestSnapshot(unittest.TestCase):
    def setUp(self):
        self._counter = 0
        def mem_fn():
            self._counter += 1000
            return self._counter
        self.t = MemoryTracker(get_memory_fn=mem_fn)

    def test_first_snapshot_delta_is_rss(self):
        s = self.t.snapshot("first")
        self.assertEqual(s.rss_bytes, 1000)
        self.assertEqual(s.delta_bytes, 1000)  # no previous, delta = rss - 0

    def test_second_snapshot_delta(self):
        self.t.snapshot("a")
        s2 = self.t.snapshot("b")
        self.assertEqual(s2.delta_bytes, 1000)

    def test_label_stored(self):
        s = self.t.snapshot("my_label")
        self.assertEqual(s.label, "my_label")

    def test_empty_label(self):
        s = self.t.snapshot()
        self.assertEqual(s.label, "")

    def test_timestamp_set(self):
        s = self.t.snapshot("t")
        self.assertGreater(s.timestamp, 0)


class TestTrackContextManager(unittest.TestCase):
    def test_track_creates_two_snapshots(self):
        val = [1000]
        def mem_fn():
            v = val[0]
            val[0] += 500
            return v
        t = MemoryTracker(get_memory_fn=mem_fn)
        with t.track("op"):
            pass
        self.assertEqual(len(t.snapshots), 2)
        self.assertEqual(t.snapshots[0].label, "op:before")
        self.assertEqual(t.snapshots[1].label, "op:after")

    def test_track_exception_still_records(self):
        t = MemoryTracker(get_memory_fn=lambda: 100)
        try:
            with t.track("fail"):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        self.assertEqual(len(t.snapshots), 2)


class TestSnapshots(unittest.TestCase):
    def test_returns_copy(self):
        t = MemoryTracker(get_memory_fn=lambda: 100)
        t.snapshot("a")
        snaps = t.snapshots
        snaps.clear()
        self.assertEqual(len(t.snapshots), 1)

    def test_empty_initially(self):
        t = MemoryTracker(get_memory_fn=lambda: 0)
        self.assertEqual(t.snapshots, [])


class TestPeak(unittest.TestCase):
    def test_peak_none_when_empty(self):
        t = MemoryTracker(get_memory_fn=lambda: 0)
        self.assertIsNone(t.peak())

    def test_peak_returns_highest(self):
        values = iter([100, 300, 200])
        t = MemoryTracker(get_memory_fn=lambda: next(values))
        t.snapshot("a")
        t.snapshot("b")
        t.snapshot("c")
        p = t.peak()
        self.assertIsNotNone(p)
        self.assertEqual(p.rss_bytes, 300)


class TestGrowth(unittest.TestCase):
    def test_growth_empty(self):
        t = MemoryTracker(get_memory_fn=lambda: 0)
        self.assertEqual(t.growth(), 0)

    def test_growth_total(self):
        values = iter([100, 500])
        t = MemoryTracker(get_memory_fn=lambda: next(values))
        t.snapshot("a")
        t.snapshot("b")
        self.assertEqual(t.growth(), 400)

    def test_growth_since_label(self):
        values = iter([100, 300, 700])
        t = MemoryTracker(get_memory_fn=lambda: next(values))
        t.snapshot("start")
        t.snapshot("mid")
        t.snapshot("end")
        self.assertEqual(t.growth(since_label="mid"), 400)

    def test_growth_unknown_label(self):
        t = MemoryTracker(get_memory_fn=lambda: 100)
        t.snapshot("a")
        self.assertEqual(t.growth(since_label="nonexistent"), 0)


class TestFormatReport(unittest.TestCase):
    def test_empty_report(self):
        t = MemoryTracker(get_memory_fn=lambda: 0)
        self.assertIn("No snapshots", t.format_report())

    def test_report_contains_labels(self):
        values = iter([1024, 2048])
        t = MemoryTracker(get_memory_fn=lambda: next(values))
        t.snapshot("first")
        t.snapshot("second")
        report = t.format_report()
        self.assertIn("first", report)
        self.assertIn("second", report)
        self.assertIn("Peak", report)
        self.assertIn("growth", report.lower())


class TestClear(unittest.TestCase):
    def test_clear(self):
        t = MemoryTracker(get_memory_fn=lambda: 100)
        t.snapshot("a")
        t.clear()
        self.assertEqual(t.snapshots, [])


class TestFmtBytes(unittest.TestCase):
    def test_bytes(self):
        self.assertIn("B", _fmt_bytes(500))

    def test_kilobytes(self):
        self.assertIn("KB", _fmt_bytes(2048))

    def test_megabytes(self):
        self.assertIn("MB", _fmt_bytes(2 * 1024 * 1024))

    def test_negative(self):
        result = _fmt_bytes(-2048)
        self.assertIn("KB", result)


if __name__ == "__main__":
    unittest.main()
