"""Tests for lidco.profiler.runner."""
from __future__ import annotations

import time
import unittest

from lidco.profiler.runner import ProfileResult, ProfileRunner


class TestProfileResult(unittest.TestCase):
    def test_defaults(self):
        r = ProfileResult(name="test", total_time=1.0, call_count=5)
        self.assertEqual(r.name, "test")
        self.assertEqual(r.total_time, 1.0)
        self.assertEqual(r.call_count, 5)
        self.assertIsInstance(r.entries, list)
        self.assertGreater(r.timestamp, 0.0)

    def test_auto_timestamp(self):
        before = time.time()
        r = ProfileResult(name="t", total_time=0, call_count=0)
        self.assertGreaterEqual(r.timestamp, before)

    def test_explicit_timestamp(self):
        r = ProfileResult(name="t", total_time=0, call_count=0, timestamp=42.0)
        self.assertEqual(r.timestamp, 42.0)


class TestProfileRunner(unittest.TestCase):
    def setUp(self):
        self.runner = ProfileRunner()

    def test_profile_basic(self):
        result = self.runner.profile("x = 1\ny = 2")
        self.assertIsInstance(result, ProfileResult)
        self.assertGreater(result.total_time, 0)
        self.assertEqual(len(result.entries), 2)

    def test_profile_auto_name(self):
        result = self.runner.profile("a = 1")
        self.assertTrue(len(result.name) > 0)

    def test_profile_custom_name(self):
        result = self.runner.profile("a = 1", name="myprof")
        self.assertEqual(result.name, "myprof")

    def test_profile_call_count(self):
        result = self.runner.profile("foo()\nbar()\nx = 1")
        self.assertEqual(result.call_count, 2)

    def test_history(self):
        self.runner.profile("a = 1")
        self.runner.profile("b = 2")
        self.assertEqual(len(self.runner.history()), 2)

    def test_latest(self):
        self.assertIsNone(self.runner.latest())
        self.runner.profile("a = 1", name="first")
        self.runner.profile("b = 2", name="second")
        self.assertEqual(self.runner.latest().name, "second")

    def test_clear(self):
        self.runner.profile("a = 1")
        count = self.runner.clear()
        self.assertEqual(count, 1)
        self.assertEqual(len(self.runner.history()), 0)

    def test_compare(self):
        a = self.runner.profile("x = 1", name="a")
        b = self.runner.profile("x = 1\ny = 2\nz = 3", name="b")
        cmp = self.runner.compare(a, b)
        self.assertEqual(cmp["a_name"], "a")
        self.assertEqual(cmp["b_name"], "b")
        self.assertIn("speedup", cmp)
        self.assertIn("time_diff", cmp)

    def test_summary_empty(self):
        s = self.runner.summary()
        self.assertEqual(s["runs"], 0)

    def test_summary(self):
        self.runner.profile("a = 1")
        self.runner.profile("b = 2")
        s = self.runner.summary()
        self.assertEqual(s["runs"], 2)
        self.assertGreater(s["avg_time"], 0)


if __name__ == "__main__":
    unittest.main()
