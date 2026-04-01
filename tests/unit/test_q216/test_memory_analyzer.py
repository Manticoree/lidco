"""Tests for perf_intel.memory_analyzer."""
from __future__ import annotations

import unittest

from lidco.perf_intel.memory_analyzer import MemoryAnalyzer, MemoryIssue


class TestMemoryIssue(unittest.TestCase):
    def test_frozen(self):
        m = MemoryIssue(issue_type="leak")
        with self.assertRaises(AttributeError):
            m.issue_type = "other"  # type: ignore[misc]

    def test_defaults(self):
        m = MemoryIssue(issue_type="leak")
        self.assertEqual(m.file, "")
        self.assertEqual(m.severity, "medium")
        self.assertEqual(m.pattern, "")


class TestMemoryAnalyzer(unittest.TestCase):
    def test_detect_circular_refs(self):
        source = """\
class Node:
    def __init__(self):
        self.parent = self
"""
        analyzer = MemoryAnalyzer()
        results = analyzer._detect_circular_refs(source, "node.py")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].issue_type, "circular_reference")
        self.assertEqual(results[0].severity, "high")

    def test_no_circular_refs(self):
        source = "self.name = 'hello'\n"
        analyzer = MemoryAnalyzer()
        results = analyzer._detect_circular_refs(source, "ok.py")
        self.assertEqual(results, [])

    def test_detect_growing_collections(self):
        source = """\
for item in stream:
    self.history.append(item)
"""
        analyzer = MemoryAnalyzer()
        results = analyzer._detect_growing_collections(source, "g.py")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].issue_type, "growing_collection")

    def test_no_growing_outside_loop(self):
        source = "self.items.append(x)\n"
        analyzer = MemoryAnalyzer()
        results = analyzer._detect_growing_collections(source, "ok.py")
        self.assertEqual(results, [])

    def test_detect_unclosed_resources(self):
        source = "f = open('data.txt', 'r')\ndata = f.read()\n"
        analyzer = MemoryAnalyzer()
        results = analyzer._detect_unclosed_resources(source, "io.py")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].issue_type, "unclosed_resource")

    def test_with_statement_ok(self):
        source = "with open('data.txt') as f:\n    data = f.read()\n"
        analyzer = MemoryAnalyzer()
        results = analyzer._detect_unclosed_resources(source, "ok.py")
        self.assertEqual(results, [])

    def test_detect_leaks_combines(self):
        source = """\
class Leak:
    def __init__(self):
        self.ref = self
f = open('x.txt')
for i in range(100):
    self.buf.append(i)
"""
        analyzer = MemoryAnalyzer()
        results = analyzer.detect_leaks(source, "all.py")
        types = {r.issue_type for r in results}
        self.assertIn("circular_reference", types)
        self.assertIn("unclosed_resource", types)
        self.assertIn("growing_collection", types)

    def test_summary_empty(self):
        analyzer = MemoryAnalyzer()
        self.assertEqual(analyzer.summary([]), "No memory issues detected.")

    def test_summary_with_issues(self):
        analyzer = MemoryAnalyzer()
        issue = MemoryIssue(
            issue_type="leak", file="a.py", line=1,
            description="bad", severity="high",
        )
        s = analyzer.summary([issue])
        self.assertIn("Memory issues: 1", s)
        self.assertIn("high", s)


if __name__ == "__main__":
    unittest.main()
