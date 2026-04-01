"""Tests for budget.tool_compressor."""
from __future__ import annotations

import unittest

from lidco.budget.tool_compressor import (
    CompressionRule,
    CompressedResult,
    ToolCompressor,
)


class TestCompressionRule(unittest.TestCase):
    def test_frozen(self):
        rule = CompressionRule(tool_name="X")
        with self.assertRaises(AttributeError):
            rule.tool_name = "Y"  # type: ignore[misc]

    def test_defaults(self):
        rule = CompressionRule(tool_name="T")
        self.assertEqual(rule.max_tokens, 500)
        self.assertEqual(rule.strategy, "truncate")


class TestCompressedResult(unittest.TestCase):
    def test_frozen(self):
        r = CompressedResult(original_tokens=100, compressed_tokens=50)
        with self.assertRaises(AttributeError):
            r.truncated = True  # type: ignore[misc]


class TestToolCompressor(unittest.TestCase):
    def setUp(self):
        self.tc = ToolCompressor()

    def test_no_compress_small(self):
        content = "short output"
        _, stats = self.tc.compress("Read", content)
        self.assertFalse(stats.truncated)

    def test_compress_read_head_tail(self):
        lines = [f"line {i}: " + "a" * 50 for i in range(200)]
        content = "\n".join(lines)
        compressed, stats = self.tc.compress("Read", content)
        self.assertTrue(stats.truncated)
        self.assertIn("omitted", compressed)

    def test_compress_grep_top_n(self):
        lines = [f"match {i}: " + "x" * 40 for i in range(100)]
        content = "\n".join(lines)
        compressed, stats = self.tc.compress("Grep", content)
        self.assertTrue(stats.truncated)
        self.assertIn("omitted", compressed)

    def test_compress_bash_head_tail(self):
        content = "output\n" * 500
        compressed, stats = self.tc.compress("Bash", content)
        self.assertTrue(stats.truncated)

    def test_compress_glob_truncate(self):
        content = "file.py\n" * 300
        compressed, stats = self.tc.compress("Glob", content)
        self.assertTrue(stats.truncated)
        self.assertIn("[truncated]", compressed)

    def test_compress_unknown_tool(self):
        content = "x" * 10000
        result, stats = self.tc.compress("UnknownTool", content)
        self.assertFalse(stats.truncated)
        self.assertEqual(result, content)

    def test_add_rule(self):
        rule = CompressionRule(tool_name="Custom", max_tokens=100, strategy="truncate")
        self.tc.add_rule(rule)
        content = "x" * 2000
        _, stats = self.tc.compress("Custom", content)
        self.assertTrue(stats.truncated)

    def test_compress_messages_keeps_recent(self):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "tool", "name": "Read", "content": "x" * 5000},
            {"role": "tool", "name": "Read", "content": "y" * 5000},
            {"role": "tool", "name": "Read", "content": "z" * 100},
        ]
        result, saved = self.tc.compress_messages(msgs, keep_recent=2)
        self.assertEqual(len(result), 4)
        # First tool msg compressed, last 2 kept
        first_tool = result[1]["content"]
        self.assertTrue(
            "[truncated]" in first_tool or "[omitted]" in first_tool,
            "Expected compression marker in first tool result",
        )
        self.assertGreater(saved, 0)

    def test_compress_messages_no_tool(self):
        msgs = [{"role": "user", "content": "hi"}]
        result, saved = self.tc.compress_messages(msgs)
        self.assertEqual(saved, 0)
        self.assertEqual(len(result), 1)

    def test_estimate_tokens(self):
        self.assertEqual(self.tc.estimate_tokens("abcd"), 1)
        self.assertEqual(self.tc.estimate_tokens("a" * 100), 25)

    def test_summary(self):
        s = self.tc.summary()
        self.assertIn("4 rules", s)
        self.assertIn("Read", s)


if __name__ == "__main__":
    unittest.main()
