"""Tests for ComplexityAnalyzer, ComplexityResult."""
from __future__ import annotations

import unittest

from lidco.project_analytics.complexity_analyzer import (
    ComplexityAnalyzer,
    ComplexityResult,
)


class TestComplexityResult(unittest.TestCase):
    def test_frozen(self):
        r = ComplexityResult(name="f", file="a.py")
        with self.assertRaises(AttributeError):
            r.name = "g"  # type: ignore[misc]

    def test_defaults(self):
        r = ComplexityResult(name="f", file="a.py")
        self.assertEqual(r.cyclomatic, 0)
        self.assertEqual(r.cognitive, 0)
        self.assertEqual(r.lines, 0)
        self.assertAlmostEqual(r.maintainability, 100.0)


class TestComplexityAnalyzer(unittest.TestCase):
    def test_simple_function(self):
        source = "def foo():\n    return 1\n"
        analyzer = ComplexityAnalyzer()
        result = analyzer.analyze_function(source, name="foo")
        self.assertEqual(result.name, "foo")
        self.assertEqual(result.cyclomatic, 1)
        self.assertEqual(result.lines, 2)

    def test_branching_function(self):
        source = (
            "def bar(x):\n"
            "    if x > 0:\n"
            "        return 1\n"
            "    elif x < 0:\n"
            "        return -1\n"
            "    return 0\n"
        )
        analyzer = ComplexityAnalyzer()
        result = analyzer.analyze_function(source, name="bar")
        self.assertGreaterEqual(result.cyclomatic, 3)

    def test_count_branches(self):
        analyzer = ComplexityAnalyzer()
        source = "if a and b or c:\n    for x in y:\n        while True:\n            pass\n"
        count = analyzer._count_branches(source)
        # if, and, or, for, while = 5
        self.assertEqual(count, 5)

    def test_count_nesting(self):
        analyzer = ComplexityAnalyzer()
        source = "if x:\n    if y:\n        if z:\n            pass\n"
        depth = analyzer._count_nesting(source)
        self.assertGreaterEqual(depth, 3)

    def test_analyze_module(self):
        source = (
            "def foo():\n    return 1\n\n"
            "def bar(x):\n    if x:\n        return 2\n    return 3\n"
        )
        analyzer = ComplexityAnalyzer()
        results = analyzer.analyze_module(source, file="mod.py")
        self.assertEqual(len(results), 2)
        names = [r.name for r in results]
        self.assertIn("foo", names)
        self.assertIn("bar", names)

    def test_hotspots(self):
        results = [
            ComplexityResult(name="a", file="x.py", cyclomatic=10),
            ComplexityResult(name="b", file="x.py", cyclomatic=2),
            ComplexityResult(name="c", file="x.py", cyclomatic=15),
        ]
        analyzer = ComplexityAnalyzer()
        top = analyzer.hotspots(results, top_n=2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0].name, "c")
        self.assertEqual(top[1].name, "a")

    def test_summary(self):
        results = [
            ComplexityResult(name="a", file="x.py", cyclomatic=5, maintainability=80.0),
            ComplexityResult(name="b", file="x.py", cyclomatic=3, maintainability=90.0),
        ]
        analyzer = ComplexityAnalyzer()
        text = analyzer.summary(results)
        self.assertIn("Functions: 2", text)
        self.assertIn("Avg cyclomatic", text)
        self.assertIn("Max cyclomatic: 5", text)

    def test_summary_empty(self):
        analyzer = ComplexityAnalyzer()
        text = analyzer.summary([])
        self.assertIn("No results", text)
