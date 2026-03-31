"""Tests for TimingProfiler."""
from __future__ import annotations

import time
import unittest

from lidco.perf.timing_profiler import TimingProfiler, TimingRecord


class TestTimingRecord(unittest.TestCase):
    def test_dataclass_fields(self):
        r = TimingRecord(name="op", elapsed=0.5, started_at=1.0, ended_at=1.5)
        self.assertEqual(r.name, "op")
        self.assertAlmostEqual(r.elapsed, 0.5)
        self.assertEqual(r.metadata, {})

    def test_metadata_default_factory(self):
        r1 = TimingRecord(name="a", elapsed=0, started_at=0, ended_at=0)
        r2 = TimingRecord(name="b", elapsed=0, started_at=0, ended_at=0)
        r1.metadata["key"] = "val"
        self.assertNotIn("key", r2.metadata)

    def test_metadata_custom(self):
        r = TimingRecord(name="x", elapsed=0, started_at=0, ended_at=0, metadata={"k": 1})
        self.assertEqual(r.metadata["k"], 1)


class TestTimingProfilerStartStop(unittest.TestCase):
    def setUp(self):
        self.p = TimingProfiler()

    def test_start_returns_string_id(self):
        tid = self.p.start("op")
        self.assertIsInstance(tid, str)
        self.assertTrue(len(tid) > 0)

    def test_stop_returns_record(self):
        tid = self.p.start("op")
        rec = self.p.stop(tid)
        self.assertIsInstance(rec, TimingRecord)
        self.assertEqual(rec.name, "op")
        self.assertGreaterEqual(rec.elapsed, 0)

    def test_stop_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            self.p.stop("nonexistent")

    def test_stop_same_id_twice_raises(self):
        tid = self.p.start("op")
        self.p.stop(tid)
        with self.assertRaises(KeyError):
            self.p.stop(tid)

    def test_elapsed_positive(self):
        tid = self.p.start("op")
        time.sleep(0.01)
        rec = self.p.stop(tid)
        self.assertGreater(rec.elapsed, 0)

    def test_multiple_timers(self):
        t1 = self.p.start("a")
        t2 = self.p.start("b")
        r2 = self.p.stop(t2)
        r1 = self.p.stop(t1)
        self.assertEqual(r1.name, "a")
        self.assertEqual(r2.name, "b")


class TestMeasureContextManager(unittest.TestCase):
    def setUp(self):
        self.p = TimingProfiler()

    def test_measure_adds_record(self):
        with self.p.measure("op"):
            pass
        self.assertEqual(len(self.p.records), 1)
        self.assertEqual(self.p.records[0].name, "op")

    def test_measure_timing(self):
        with self.p.measure("slow"):
            time.sleep(0.01)
        self.assertGreater(self.p.records[0].elapsed, 0)

    def test_measure_exception_still_records(self):
        try:
            with self.p.measure("fail"):
                raise ValueError("boom")
        except ValueError:
            pass
        self.assertEqual(len(self.p.records), 1)


class TestDecorator(unittest.TestCase):
    def setUp(self):
        self.p = TimingProfiler()

    def test_decorator_uses_function_name(self):
        @self.p.decorator()
        def my_func():
            return 42

        result = my_func()
        self.assertEqual(result, 42)
        self.assertEqual(len(self.p.records), 1)
        self.assertEqual(self.p.records[0].name, "my_func")

    def test_decorator_custom_name(self):
        @self.p.decorator(name="custom")
        def fn():
            pass

        fn()
        self.assertEqual(self.p.records[0].name, "custom")

    def test_decorator_preserves_return_value(self):
        @self.p.decorator()
        def add(a, b):
            return a + b

        self.assertEqual(add(3, 4), 7)

    def test_decorator_multiple_calls(self):
        @self.p.decorator()
        def noop():
            pass

        noop()
        noop()
        noop()
        self.assertEqual(len(self.p.records), 3)


class TestRecordsAndSummary(unittest.TestCase):
    def setUp(self):
        self.p = TimingProfiler()

    def test_records_empty_initially(self):
        self.assertEqual(self.p.records, [])

    def test_records_returns_copy(self):
        with self.p.measure("a"):
            pass
        recs = self.p.records
        recs.clear()
        self.assertEqual(len(self.p.records), 1)

    def test_summary_empty(self):
        self.assertEqual(self.p.summary(), {})

    def test_summary_structure(self):
        with self.p.measure("op"):
            pass
        s = self.p.summary()
        self.assertIn("op", s)
        self.assertIn("avg", s["op"])
        self.assertIn("min", s["op"])
        self.assertIn("max", s["op"])
        self.assertIn("count", s["op"])
        self.assertIn("total", s["op"])
        self.assertEqual(s["op"]["count"], 1.0)

    def test_summary_multiple_same_name(self):
        for _ in range(3):
            with self.p.measure("op"):
                pass
        s = self.p.summary()
        self.assertEqual(s["op"]["count"], 3.0)
        self.assertLessEqual(s["op"]["min"], s["op"]["avg"])
        self.assertLessEqual(s["op"]["avg"], s["op"]["max"])


class TestSlowest(unittest.TestCase):
    def test_slowest_empty(self):
        p = TimingProfiler()
        self.assertEqual(p.slowest(), [])

    def test_slowest_order(self):
        p = TimingProfiler()
        # Manually inject records for deterministic test
        p._records = [
            TimingRecord(name="fast", elapsed=0.01, started_at=0, ended_at=0.01),
            TimingRecord(name="slow", elapsed=1.0, started_at=0, ended_at=1.0),
            TimingRecord(name="medium", elapsed=0.5, started_at=0, ended_at=0.5),
        ]
        result = p.slowest(2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, "slow")
        self.assertEqual(result[1].name, "medium")

    def test_slowest_default_n(self):
        p = TimingProfiler()
        for i in range(10):
            p._records.append(TimingRecord(name=f"op{i}", elapsed=float(i), started_at=0, ended_at=0))
        self.assertEqual(len(p.slowest()), 5)


class TestClear(unittest.TestCase):
    def test_clear_removes_records(self):
        p = TimingProfiler()
        with p.measure("op"):
            pass
        p.clear()
        self.assertEqual(p.records, [])

    def test_clear_removes_active(self):
        p = TimingProfiler()
        tid = p.start("op")
        p.clear()
        with self.assertRaises(KeyError):
            p.stop(tid)


if __name__ == "__main__":
    unittest.main()
