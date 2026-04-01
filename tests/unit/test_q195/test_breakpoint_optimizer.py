"""Tests for cache.breakpoint_optimizer — Breakpoint, BreakpointOptimizer."""
from __future__ import annotations

import unittest

from lidco.cache.breakpoint_optimizer import Breakpoint, BreakpointOptimizer


class TestBreakpoint(unittest.TestCase):
    def test_frozen(self):
        b = Breakpoint(position=100, savings_estimate=0.5, description="test")
        with self.assertRaises(AttributeError):
            b.position = 200  # type: ignore[misc]

    def test_fields(self):
        b = Breakpoint(50, 0.25, "paragraph boundary")
        self.assertEqual(b.position, 50)
        self.assertAlmostEqual(b.savings_estimate, 0.25)
        self.assertEqual(b.description, "paragraph boundary")

    def test_equality(self):
        a = Breakpoint(10, 0.1, "x")
        b = Breakpoint(10, 0.1, "x")
        self.assertEqual(a, b)


class TestBreakpointOptimizer(unittest.TestCase):
    def test_analyze_empty(self):
        opt = BreakpointOptimizer()
        result = opt.analyze("")
        self.assertEqual(result, ())

    def test_analyze_finds_paragraph_boundaries(self):
        prompt = "Line one\n\nLine three\n\nLine five"
        opt = BreakpointOptimizer()
        bps = opt.analyze(prompt)
        self.assertGreater(len(bps), 0)
        for bp in bps:
            self.assertIn("paragraph", bp.description.lower())

    def test_analyze_finds_headers(self):
        prompt = "# Header\nContent\n## Subheader\nMore content"
        opt = BreakpointOptimizer()
        bps = opt.analyze(prompt)
        descriptions = [bp.description for bp in bps]
        self.assertTrue(any("section header" in d for d in descriptions))

    def test_analyze_with_prefix_len(self):
        prompt = "Part 1\n\nPart 2\n\nPart 3"
        opt = BreakpointOptimizer()
        full_bps = opt.analyze(prompt)
        partial_bps = opt.analyze(prompt, cache_prefix_len=100)
        self.assertGreaterEqual(len(full_bps), len(partial_bps))

    def test_analyze_returns_tuple(self):
        opt = BreakpointOptimizer()
        result = opt.analyze("some text")
        self.assertIsInstance(result, tuple)

    def test_optimal_split_single_part(self):
        opt = BreakpointOptimizer()
        result = opt.optimal_split("hello", 1)
        self.assertEqual(result, ("hello",))

    def test_optimal_split_empty(self):
        opt = BreakpointOptimizer()
        result = opt.optimal_split("", 2)
        self.assertEqual(result, ("",))

    def test_optimal_split_two_parts(self):
        prompt = "Part A.\n\nPart B.\n\nPart C."
        opt = BreakpointOptimizer()
        result = opt.optimal_split(prompt, 2)
        self.assertGreaterEqual(len(result), 1)
        # Reassembled should match original
        reassembled = "".join(result)
        self.assertEqual(reassembled, prompt)

    def test_optimal_split_no_breakpoints(self):
        prompt = "single continuous line"
        opt = BreakpointOptimizer()
        result = opt.optimal_split(prompt, 2)
        self.assertGreaterEqual(len(result), 1)
        self.assertEqual("".join(result), prompt)

    def test_savings_estimate_range(self):
        prompt = "A\n\nB\n\nC\n\nD"
        opt = BreakpointOptimizer()
        bps = opt.analyze(prompt)
        for bp in bps:
            self.assertGreaterEqual(bp.savings_estimate, 0.0)
            self.assertLessEqual(bp.savings_estimate, 1.0)

    def test_breakpoint_positions_positive(self):
        prompt = "# Title\n\nContent here\n\n## Section\nMore text"
        opt = BreakpointOptimizer()
        bps = opt.analyze(prompt)
        for bp in bps:
            self.assertGreater(bp.position, 0)

    def test_analyze_separator_line(self):
        prompt = "Above\n---\nBelow"
        opt = BreakpointOptimizer()
        bps = opt.analyze(prompt)
        descriptions = [bp.description for bp in bps]
        self.assertTrue(any("section" in d for d in descriptions))

    def test_optimal_split_three_parts(self):
        prompt = "A\n\nB\n\nC\n\nD\n\nE"
        opt = BreakpointOptimizer()
        result = opt.optimal_split(prompt, 3)
        self.assertGreaterEqual(len(result), 1)
        self.assertEqual("".join(result), prompt)

    def test_breakpoint_different_not_equal(self):
        a = Breakpoint(10, 0.1, "x")
        b = Breakpoint(20, 0.1, "x")
        self.assertNotEqual(a, b)

    def test_analyze_no_boundaries(self):
        prompt = "one two three four five"
        opt = BreakpointOptimizer()
        bps = opt.analyze(prompt)
        self.assertEqual(len(bps), 0)


class TestBreakpointOptimizerAllExport(unittest.TestCase):
    def test_all(self):
        from lidco.cache import breakpoint_optimizer

        self.assertIn("Breakpoint", breakpoint_optimizer.__all__)
        self.assertIn("BreakpointOptimizer", breakpoint_optimizer.__all__)


if __name__ == "__main__":
    unittest.main()
