"""Tests for context.incremental_compactor — CompactionResult, IncrementalCompactor."""
from __future__ import annotations

import unittest

from lidco.context.incremental_compactor import CompactionResult, IncrementalCompactor


class TestCompactionResult(unittest.TestCase):
    def test_frozen(self):
        r = CompactionResult()
        with self.assertRaises(AttributeError):
            r.watermark = 5  # type: ignore[misc]

    def test_defaults(self):
        r = CompactionResult()
        self.assertEqual(r.compacted, ())
        self.assertEqual(r.removed_count, 0)
        self.assertEqual(r.saved_tokens, 0)
        self.assertEqual(r.watermark, 0)


class TestIncrementalCompactor(unittest.TestCase):
    def test_empty_messages(self):
        c = IncrementalCompactor()
        result = c.compact([], target_tokens=100)
        self.assertEqual(result.compacted, ())

    def test_under_budget_no_change(self):
        c = IncrementalCompactor()
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        result = c.compact(msgs, target_tokens=9999)
        self.assertEqual(len(result.compacted), 2)

    def test_tool_results_summarized(self):
        c = IncrementalCompactor()
        msgs = [
            {"role": "user", "content": "run tool"},
            {"role": "tool", "content": "Line 1\nLine 2\nLine 3\n" * 50},
        ]
        result = c.compact(msgs, target_tokens=10)
        tool_msg = [m for m in result.compacted if m.get("role") == "tool"]
        if tool_msg:
            self.assertLess(len(tool_msg[0]["content"]), 200)

    def test_watermark_advances(self):
        c = IncrementalCompactor()
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "a" * 400},
            {"role": "tool", "content": "result " * 100},
        ]
        result = c.compact(msgs, target_tokens=20)
        self.assertGreater(result.watermark, 0)

    def test_system_messages_preserved(self):
        c = IncrementalCompactor()
        msgs = [
            {"role": "system", "content": "important system prompt"},
            {"role": "assistant", "content": "x" * 800},
            {"role": "tool", "content": "big result\n" * 100},
        ]
        result = c.compact(msgs, target_tokens=10)
        roles = [m["role"] for m in result.compacted]
        self.assertIn("system", roles)

    def test_merge_tool_results(self):
        c = IncrementalCompactor()
        msgs = [
            {"role": "tool", "content": "result A"},
            {"role": "tool", "content": "result B"},
            {"role": "user", "content": "next"},
        ]
        merged = c.merge_tool_results(msgs)
        self.assertEqual(len(merged), 2)
        self.assertIn("result A", merged[0]["content"])
        self.assertIn("result B", merged[0]["content"])

    def test_merge_tool_results_empty(self):
        c = IncrementalCompactor()
        self.assertEqual(c.merge_tool_results([]), [])

    def test_estimate_tokens(self):
        c = IncrementalCompactor()
        msgs = [{"role": "user", "content": "a" * 100}]
        self.assertEqual(c.estimate_tokens(msgs), 25)

    def test_estimate_tokens_minimum(self):
        c = IncrementalCompactor()
        msgs = [{"role": "user", "content": "hi"}]
        self.assertEqual(c.estimate_tokens(msgs), 1)

    def test_original_not_mutated(self):
        c = IncrementalCompactor()
        original = [
            {"role": "user", "content": "q"},
            {"role": "tool", "content": "long " * 200},
        ]
        original_copy = [dict(m) for m in original]
        c.compact(original, target_tokens=5)
        self.assertEqual(original, original_copy)


if __name__ == "__main__":
    unittest.main()
