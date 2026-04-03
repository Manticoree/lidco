"""Tests for lidco.prompts.debugger (Q246)."""
from __future__ import annotations

import unittest

from lidco.prompts.debugger import PromptDebugger


class TestPromptDebuggerRecord(unittest.TestCase):
    def test_record_turn(self):
        dbg = PromptDebugger()
        dbg.record_turn("prompt1", "response1")
        self.assertEqual(len(dbg.history()), 1)

    def test_record_multiple(self):
        dbg = PromptDebugger()
        dbg.record_turn("p1", "r1")
        dbg.record_turn("p2", "r2")
        self.assertEqual(len(dbg.history()), 2)


class TestPromptDebuggerDiff(unittest.TestCase):
    def test_diff_identical(self):
        dbg = PromptDebugger()
        dbg.record_turn("line1\nline2", "r")
        dbg.record_turn("line1\nline2", "r")
        result = dbg.diff(0, 1)
        self.assertTrue(all(l.startswith(" ") for l in result))

    def test_diff_different(self):
        dbg = PromptDebugger()
        dbg.record_turn("line1\nold", "r")
        dbg.record_turn("line1\nnew", "r")
        result = dbg.diff(0, 1)
        self.assertTrue(any(l.startswith("-") for l in result))
        self.assertTrue(any(l.startswith("+") for l in result))

    def test_diff_out_of_range(self):
        dbg = PromptDebugger()
        result = dbg.diff(0, 1)
        self.assertTrue(len(result) > 0)
        self.assertIn("out of range", result[0])

    def test_diff_added_lines(self):
        dbg = PromptDebugger()
        dbg.record_turn("a", "r")
        dbg.record_turn("a\nb", "r")
        result = dbg.diff(0, 1)
        self.assertTrue(any(l.startswith("+") for l in result))

    def test_diff_removed_lines(self):
        dbg = PromptDebugger()
        dbg.record_turn("a\nb", "r")
        dbg.record_turn("a", "r")
        result = dbg.diff(0, 1)
        self.assertTrue(any(l.startswith("-") for l in result))


class TestPromptDebuggerTokenBreakdown(unittest.TestCase):
    def test_token_breakdown(self):
        dbg = PromptDebugger()
        dbg.record_turn("A" * 40, "B" * 20)
        bd = dbg.token_breakdown(0)
        self.assertEqual(bd["prompt_tokens"], 10)
        self.assertEqual(bd["response_tokens"], 5)
        self.assertEqual(bd["total"], 15)

    def test_token_breakdown_out_of_range(self):
        dbg = PromptDebugger()
        self.assertEqual(dbg.token_breakdown(0), {})

    def test_token_breakdown_minimum_one(self):
        dbg = PromptDebugger()
        dbg.record_turn("Hi", "Ok")
        bd = dbg.token_breakdown(0)
        self.assertGreaterEqual(bd["prompt_tokens"], 1)
        self.assertGreaterEqual(bd["response_tokens"], 1)


class TestPromptDebuggerShowTurn(unittest.TestCase):
    def test_show_turn(self):
        dbg = PromptDebugger()
        dbg.record_turn("prompt", "response")
        info = dbg.show_turn(0)
        self.assertIsNotNone(info)
        self.assertEqual(info["prompt"], "prompt")
        self.assertEqual(info["response"], "response")
        self.assertIn("tokens", info)

    def test_show_turn_out_of_range(self):
        dbg = PromptDebugger()
        self.assertIsNone(dbg.show_turn(0))

    def test_show_turn_negative(self):
        dbg = PromptDebugger()
        dbg.record_turn("p", "r")
        self.assertIsNone(dbg.show_turn(-1))


class TestPromptDebuggerHistory(unittest.TestCase):
    def test_history_empty(self):
        dbg = PromptDebugger()
        self.assertEqual(dbg.history(), [])

    def test_history_structure(self):
        dbg = PromptDebugger()
        dbg.record_turn("p", "r")
        h = dbg.history()
        self.assertEqual(h[0]["turn"], 0)
        self.assertIn("prompt_len", h[0])
        self.assertIn("response_len", h[0])
        self.assertIn("tokens", h[0])


class TestPromptDebuggerHighlight(unittest.TestCase):
    def test_highlight_injected(self):
        dbg = PromptDebugger()
        dbg.record_turn("Hello SYSTEM world", "r")
        result = dbg.highlight_injected(0, ["SYSTEM"])
        self.assertIn("[INJECTED: SYSTEM]", result)

    def test_highlight_multiple_markers(self):
        dbg = PromptDebugger()
        dbg.record_turn("A and B", "r")
        result = dbg.highlight_injected(0, ["A", "B"])
        self.assertIn("[INJECTED: A]", result)
        self.assertIn("[INJECTED: B]", result)

    def test_highlight_out_of_range(self):
        dbg = PromptDebugger()
        result = dbg.highlight_injected(5, ["x"])
        self.assertEqual(result, "")

    def test_highlight_no_match(self):
        dbg = PromptDebugger()
        dbg.record_turn("Hello world", "r")
        result = dbg.highlight_injected(0, ["MISSING"])
        self.assertEqual(result, "Hello world")


if __name__ == "__main__":
    unittest.main()
