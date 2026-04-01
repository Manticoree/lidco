"""Tests for perf_intel.optimization_advisor."""
from __future__ import annotations

import unittest

from lidco.perf_intel.optimization_advisor import (
    Optimization,
    OptimizationAdvisor,
    OptimizationType,
)


class TestOptimizationType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(OptimizationType.CACHING, "caching")
        self.assertEqual(OptimizationType.PARALLELIZATION, "parallelization")


class TestOptimization(unittest.TestCase):
    def test_frozen(self):
        o = Optimization(type=OptimizationType.CACHING, target="f", description="d")
        with self.assertRaises(AttributeError):
            o.target = "x"  # type: ignore[misc]

    def test_defaults(self):
        o = Optimization(type=OptimizationType.BATCHING, target="t", description="d")
        self.assertEqual(o.estimated_impact, "medium")
        self.assertEqual(o.code_snippet, "")


class TestOptimizationAdvisor(unittest.TestCase):
    def test_suggest_caching(self):
        source = """\
x = compute(1)
y = compute(1)
z = compute(1)
"""
        advisor = OptimizationAdvisor()
        results = advisor.suggest_caching(source)
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].type, OptimizationType.CACHING)

    def test_suggest_caching_no_repeat(self):
        source = "x = compute(1)\ny = other(2)\n"
        advisor = OptimizationAdvisor()
        results = advisor.suggest_caching(source)
        self.assertEqual(results, [])

    def test_suggest_batching(self):
        source = """\
for item in items:
    db.execute(item)
"""
        advisor = OptimizationAdvisor()
        results = advisor.suggest_batching(source)
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].type, OptimizationType.BATCHING)

    def test_suggest_batching_no_io(self):
        source = """\
for item in items:
    result.append(item)
"""
        advisor = OptimizationAdvisor()
        results = advisor.suggest_batching(source)
        self.assertEqual(results, [])

    def test_analyze_combines(self):
        source = """\
compute(1)
compute(1)
compute(1)
for item in items:
    api.call(item)
"""
        advisor = OptimizationAdvisor()
        results = advisor.analyze(source)
        types = {o.type for o in results}
        self.assertIn(OptimizationType.CACHING, types)
        self.assertIn(OptimizationType.BATCHING, types)

    def test_summary_empty(self):
        advisor = OptimizationAdvisor()
        self.assertEqual(advisor.summary([]), "No optimizations suggested.")

    def test_summary_with_results(self):
        advisor = OptimizationAdvisor()
        o = Optimization(
            type=OptimizationType.CACHING, target="f()", description="cache me",
        )
        s = advisor.summary([o])
        self.assertIn("Optimizations: 1", s)
        self.assertIn("caching", s)

    def test_analyze_empty_source(self):
        advisor = OptimizationAdvisor()
        results = advisor.analyze("")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
