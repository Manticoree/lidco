"""Tests for perf_intel.bottleneck_detector."""
from __future__ import annotations

import unittest

from lidco.perf_intel.bottleneck_detector import (
    Bottleneck,
    BottleneckDetector,
    BottleneckType,
)


class TestBottleneckType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(BottleneckType.QUADRATIC_LOOP, "quadratic_loop")
        self.assertEqual(BottleneckType.BLOCKING_IO, "blocking_io")


class TestBottleneck(unittest.TestCase):
    def test_frozen(self):
        b = Bottleneck(type=BottleneckType.QUADRATIC_LOOP, file="a.py")
        with self.assertRaises(AttributeError):
            b.file = "b.py"  # type: ignore[misc]

    def test_defaults(self):
        b = Bottleneck(type=BottleneckType.LARGE_ALLOCATION, file="x.py")
        self.assertEqual(b.line, 0)
        self.assertEqual(b.severity, "medium")


class TestBottleneckDetector(unittest.TestCase):
    def test_nested_loops(self):
        source = """\
for i in range(n):
    for j in range(n):
        process(i, j)
"""
        detector = BottleneckDetector()
        results = detector.detect(source, "test.py")
        types = [b.type for b in results]
        self.assertIn(BottleneckType.QUADRATIC_LOOP, types)

    def test_no_nested_loops(self):
        source = """\
for i in range(n):
    process(i)
for j in range(n):
    process(j)
"""
        detector = BottleneckDetector()
        results = detector._detect_nested_loops(source, "t.py")
        self.assertEqual(results, [])

    def test_repeated_calls(self):
        source = """\
for item in items:
    db.query(item)
    db.query(item)
"""
        detector = BottleneckDetector()
        results = detector._detect_repeated_calls(source, "t.py")
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].type, BottleneckType.REPEATED_CALL)

    def test_large_allocation(self):
        source = "data = [0] * 100000\n"
        detector = BottleneckDetector()
        results = detector._detect_large_allocations(source, "t.py")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].type, BottleneckType.LARGE_ALLOCATION)

    def test_small_allocation_ignored(self):
        source = "data = [0] * 100\n"
        detector = BottleneckDetector()
        results = detector._detect_large_allocations(source, "t.py")
        self.assertEqual(results, [])

    def test_summary_empty(self):
        detector = BottleneckDetector()
        self.assertEqual(detector.summary([]), "No bottlenecks detected.")

    def test_summary_with_results(self):
        detector = BottleneckDetector()
        b = Bottleneck(
            type=BottleneckType.QUADRATIC_LOOP,
            file="a.py", line=5,
            description="nested", severity="high",
        )
        s = detector.summary([b])
        self.assertIn("Bottlenecks: 1", s)
        self.assertIn("high", s)

    def test_detect_combines_all(self):
        source = """\
for i in range(n):
    for j in range(n):
        pass
data = [0] * 50000
"""
        detector = BottleneckDetector()
        results = detector.detect(source, "combo.py")
        types = {b.type for b in results}
        self.assertIn(BottleneckType.QUADRATIC_LOOP, types)
        self.assertIn(BottleneckType.LARGE_ALLOCATION, types)


if __name__ == "__main__":
    unittest.main()
