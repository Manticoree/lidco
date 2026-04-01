"""Tests for thinkback.viewer."""
from __future__ import annotations

import unittest

from lidco.thinkback.viewer import ThinkingViewer, ViewOptions


class TestViewOptions(unittest.TestCase):
    def test_frozen(self) -> None:
        opts = ViewOptions()
        with self.assertRaises(AttributeError):
            opts.collapsed = True  # type: ignore[misc]

    def test_defaults(self) -> None:
        opts = ViewOptions()
        self.assertFalse(opts.collapsed)
        self.assertEqual(opts.max_lines, 50)
        self.assertTrue(opts.highlight_decisions)
        self.assertTrue(opts.show_tokens)


class TestThinkingViewer(unittest.TestCase):
    def setUp(self) -> None:
        self.viewer = ThinkingViewer()

    def test_format_block_header(self) -> None:
        result = self.viewer.format_block("content", turn=3, tokens=50)
        self.assertIn("Turn 3", result)
        self.assertIn("50 tokens", result)

    def test_format_block_no_tokens(self) -> None:
        result = self.viewer.format_block("content", turn=1, tokens=0)
        self.assertIn("Turn 1", result)
        self.assertNotIn("tokens", result)

    def test_format_block_highlights_decisions(self) -> None:
        content = "I think\ntherefore this works\ndone"
        result = self.viewer.format_block(content, turn=1)
        self.assertIn(">>> therefore", result)

    def test_format_all(self) -> None:
        blocks = [
            {"content": "block1", "turn": 1, "tokens": 10},
            {"content": "block2", "turn": 2, "tokens": 20},
        ]
        result = self.viewer.format_all(blocks)
        self.assertIn("Turn 1", result)
        self.assertIn("Turn 2", result)

    def test_collapse_short(self) -> None:
        content = "line1\nline2\nline3"
        result = self.viewer.collapse(content, max_lines=10)
        self.assertEqual(result, content)

    def test_collapse_long(self) -> None:
        lines = [f"line {i}" for i in range(20)]
        content = "\n".join(lines)
        result = self.viewer.collapse(content, max_lines=10)
        self.assertIn("lines collapsed", result)
        self.assertIn("line 0", result)
        self.assertIn("line 19", result)

    def test_highlight_decisions(self) -> None:
        content = "normal line\nDecision: use X\nConclusion: done"
        result = self.viewer.highlight_decisions(content)
        self.assertIn(">>> Decision: use X", result)
        self.assertIn(">>> Conclusion: done", result)
        self.assertNotIn(">>> normal", result)

    def test_diff(self) -> None:
        a = "same\nold line"
        b = "same\nnew line"
        result = self.viewer.diff(a, b)
        self.assertIn("  same", result)
        self.assertIn("- old line", result)
        self.assertIn("+ new line", result)

    def test_summary(self) -> None:
        result = self.viewer.summary()
        self.assertIn("ThinkingViewer", result)

    def test_collapsed_option(self) -> None:
        opts = ViewOptions(collapsed=True, max_lines=5)
        viewer = ThinkingViewer(opts)
        lines = [f"line {i}" for i in range(20)]
        content = "\n".join(lines)
        result = viewer.format_block(content, turn=1)
        self.assertIn("collapsed", result)


if __name__ == "__main__":
    unittest.main()
