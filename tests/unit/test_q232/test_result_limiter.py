"""Tests for budget.result_limiter — ResultLimiter."""
from __future__ import annotations

import unittest

from lidco.budget.result_limiter import LimitConfig, LimitResult, ResultLimiter


class TestLimitConfig(unittest.TestCase):
    def test_frozen(self):
        c = LimitConfig(tool_name="Read")
        with self.assertRaises(AttributeError):
            c.max_tokens = 999  # type: ignore[misc]

    def test_defaults(self):
        c = LimitConfig(tool_name="x")
        self.assertEqual(c.max_tokens, 2000)
        self.assertEqual(c.min_tokens, 200)
        self.assertAlmostEqual(c.shrink_at_utilization, 0.7)


class TestLimitResult(unittest.TestCase):
    def test_frozen(self):
        r = LimitResult(tool_name="x", original_tokens=10, limited_tokens=10)
        with self.assertRaises(AttributeError):
            r.was_limited = True  # type: ignore[misc]


class TestResultLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = ResultLimiter()

    def test_no_limit_small_content(self):
        text = "hello"
        out, meta = self.limiter.apply("Read", text, utilization=0.0)
        self.assertEqual(out, text)
        self.assertFalse(meta.was_limited)

    def test_limit_large_content(self):
        text = "x" * 40_000  # 10,000 tokens, limit 2000 for Read
        out, meta = self.limiter.apply("Read", text, utilization=0.0)
        self.assertTrue(meta.was_limited)
        self.assertIn("[limited]", out)
        self.assertEqual(meta.effective_limit, 2000)

    def test_progressive_shrink(self):
        # At utilization 0.85 (midway between 0.7 and 1.0)
        limit_at_85 = self.limiter.get_limit("Read", utilization=0.85)
        # At utilization 0.0
        limit_at_0 = self.limiter.get_limit("Read", utilization=0.0)
        self.assertLess(limit_at_85, limit_at_0)

    def test_shrink_at_full_utilization(self):
        limit = self.limiter.get_limit("Read", utilization=1.0)
        # Should be at or near min_tokens (200)
        self.assertEqual(limit, 200)

    def test_no_shrink_below_threshold(self):
        limit = self.limiter.get_limit("Read", utilization=0.5)
        self.assertEqual(limit, 2000)

    def test_add_config(self):
        cfg = LimitConfig(tool_name="Custom", max_tokens=500, min_tokens=50)
        self.limiter.add_config(cfg)
        limit = self.limiter.get_limit("Custom", utilization=0.0)
        self.assertEqual(limit, 500)

    def test_default_config_for_unknown_tool(self):
        limit = self.limiter.get_limit("UnknownTool", utilization=0.0)
        self.assertEqual(limit, 2000)

    def test_estimate_tokens(self):
        self.assertEqual(self.limiter.estimate_tokens("abcdefgh"), 2)

    def test_summary(self):
        s = self.limiter.summary()
        self.assertIn("ResultLimiter", s)
        self.assertIn("Read", s)
        self.assertIn("Grep", s)

    def test_glob_lower_default_limit(self):
        limit = self.limiter.get_limit("Glob", utilization=0.0)
        self.assertEqual(limit, 500)


if __name__ == "__main__":
    unittest.main()
