"""Tests for budget.adaptive_truncator — AdaptiveTruncator."""
from __future__ import annotations

import unittest

from lidco.budget.adaptive_truncator import AdaptiveTruncator, TruncationResult


class TestTruncationResult(unittest.TestCase):
    def test_frozen(self):
        r = TruncationResult(original_tokens=100, truncated_tokens=50)
        with self.assertRaises(AttributeError):
            r.original_tokens = 200  # type: ignore[misc]

    def test_defaults(self):
        r = TruncationResult(original_tokens=10, truncated_tokens=10)
        self.assertEqual(r.strategy, "")
        self.assertFalse(r.truncated)


class TestAdaptiveTruncator(unittest.TestCase):
    def setUp(self):
        self.t = AdaptiveTruncator()

    def test_no_truncation_small_content(self):
        text = "hello"
        out, meta = self.t.truncate("Read", text, budget_remaining=10_000)
        self.assertEqual(out, text)
        self.assertFalse(meta.truncated)

    def test_head_tail_strategy_for_read(self):
        # Build content larger than Read limit (1500 tokens = 6000 chars)
        text = "\n".join(f"line {i}" for i in range(2000))
        out, meta = self.t.truncate("Read", text, budget_remaining=500)
        self.assertTrue(meta.truncated)
        self.assertEqual(meta.strategy, "head_tail")
        self.assertIn("[truncated]", out)

    def test_head_tail_strategy_for_bash(self):
        text = "\n".join(f"output {i}" for i in range(2000))
        out, meta = self.t.truncate("Bash", text, budget_remaining=400)
        self.assertTrue(meta.truncated)
        self.assertEqual(meta.strategy, "head_tail")

    def test_top_lines_strategy_for_grep(self):
        text = "\n".join(f"match {i}" for i in range(2000))
        out, meta = self.t.truncate("Grep", text, budget_remaining=300)
        self.assertTrue(meta.truncated)
        self.assertEqual(meta.strategy, "top_lines")
        self.assertIn("[truncated]", out)

    def test_hard_truncate_strategy_for_unknown(self):
        text = "x" * 20_000
        out, meta = self.t.truncate("CustomTool", text, budget_remaining=200)
        self.assertTrue(meta.truncated)
        self.assertEqual(meta.strategy, "hard_truncate")

    def test_set_limit(self):
        self.t.set_limit("Read", 500)
        # Content fitting in budget but over new limit
        text = "a" * 4000  # 1000 tokens
        out, meta = self.t.truncate("Read", text, budget_remaining=100_000)
        self.assertTrue(meta.truncated)

    def test_estimate_tokens(self):
        self.assertEqual(self.t.estimate_tokens("abcd"), 1)
        self.assertEqual(self.t.estimate_tokens("a" * 400), 100)

    def test_summary(self):
        s = self.t.summary()
        self.assertIn("AdaptiveTruncator", s)
        self.assertIn("Read", s)
        self.assertIn("Grep", s)

    def test_adaptive_max_respects_budget(self):
        text = "\n".join(f"line {i}" for i in range(2000))
        _, meta_low = self.t.truncate("Grep", text, budget_remaining=100)
        _, meta_high = self.t.truncate("Grep", text, budget_remaining=800)
        # Lower budget should produce fewer tokens
        self.assertLessEqual(meta_low.truncated_tokens, meta_high.truncated_tokens)

    def test_glob_uses_hard_truncate(self):
        text = "file\n" * 3000
        out, meta = self.t.truncate("Glob", text, budget_remaining=200)
        self.assertTrue(meta.truncated)
        self.assertEqual(meta.strategy, "hard_truncate")

    def test_content_within_budget_but_over_tool_limit(self):
        text = "a" * 8000  # 2000 tokens — over Grep limit of 1000
        _, meta = self.t.truncate("Grep", text, budget_remaining=100_000)
        self.assertTrue(meta.truncated)

    def test_no_truncation_both_fit(self):
        text = "short"
        out, meta = self.t.truncate("Grep", text, budget_remaining=100_000)
        self.assertEqual(out, text)
        self.assertFalse(meta.truncated)


if __name__ == "__main__":
    unittest.main()
