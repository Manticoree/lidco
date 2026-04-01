"""Tests for OutputFormatter — task 1075."""
from __future__ import annotations

import json
import unittest

from lidco.output.formatter import OutputFormatter


class TestFormatterInit(unittest.TestCase):
    def test_defaults(self):
        f = OutputFormatter()
        self.assertEqual(f.width, 80)
        self.assertTrue(f.use_color)

    def test_custom(self):
        f = OutputFormatter(width=120, use_color=False)
        self.assertEqual(f.width, 120)
        self.assertFalse(f.use_color)


class TestFormatMarkdown(unittest.TestCase):
    def test_h1(self):
        result = OutputFormatter().format_markdown("# Hello")
        self.assertIn("HELLO", result)

    def test_h2(self):
        result = OutputFormatter().format_markdown("## Section")
        self.assertIn("Section", result)
        self.assertIn("-", result)

    def test_h3(self):
        result = OutputFormatter().format_markdown("### Sub")
        self.assertIn("Sub", result)

    def test_bold_markers(self):
        result = OutputFormatter().format_markdown("This is **bold** text")
        self.assertIn("*bold*", result)

    def test_code_block(self):
        md = "```\ncode line\n```"
        result = OutputFormatter().format_markdown(md)
        self.assertIn("code line", result)

    def test_empty(self):
        self.assertEqual(OutputFormatter().format_markdown(""), "")


class TestFormatJson(unittest.TestCase):
    def test_dict(self):
        result = OutputFormatter().format_json({"a": 1})
        parsed = json.loads(result)
        self.assertEqual(parsed, {"a": 1})

    def test_list(self):
        result = OutputFormatter().format_json([1, 2, 3])
        parsed = json.loads(result)
        self.assertEqual(parsed, [1, 2, 3])

    def test_nested(self):
        data = {"x": {"y": [1, 2]}}
        result = OutputFormatter().format_json(data)
        self.assertIn('"y"', result)

    def test_non_serializable(self):
        from datetime import datetime
        result = OutputFormatter().format_json({"d": datetime(2026, 1, 1)})
        self.assertIn("2026", result)


class TestFormatTable(unittest.TestCase):
    def test_basic_table(self):
        result = OutputFormatter().format_table(
            [("Alice", "30"), ("Bob", "25")],
            ("Name", "Age"),
        )
        self.assertIn("Name", result)
        self.assertIn("Alice", result)
        self.assertIn("Bob", result)

    def test_empty_columns(self):
        result = OutputFormatter().format_table([], ())
        self.assertEqual(result, "")

    def test_separator(self):
        result = OutputFormatter().format_table([("x",)], ("Col",))
        self.assertIn("-", result)

    def test_column_alignment(self):
        result = OutputFormatter().format_table(
            [("short", "x"), ("longervalue", "y")],
            ("A", "B"),
        )
        lines = result.splitlines()
        self.assertEqual(len(lines), 4)  # header + sep + 2 rows


class TestFormatDiff(unittest.TestCase):
    def test_basic_diff(self):
        result = OutputFormatter().format_diff("hello", "world")
        self.assertIn("-hello", result)
        self.assertIn("+world", result)

    def test_same_content(self):
        result = OutputFormatter().format_diff("same", "same")
        self.assertIn(" same", result)
        self.assertNotIn("-same", result)

    def test_multiline(self):
        old = "a\nb\nc"
        new = "a\nB\nc"
        result = OutputFormatter().format_diff(old, new)
        self.assertIn("-b", result)
        self.assertIn("+B", result)
        self.assertIn(" a", result)


class TestTruncate(unittest.TestCase):
    def test_short_text(self):
        result = OutputFormatter().truncate("line1\nline2", 5)
        self.assertEqual(result, "line1\nline2")

    def test_truncates(self):
        text = "\n".join(f"line{i}" for i in range(20))
        result = OutputFormatter().truncate(text, 5)
        self.assertEqual(len(result.splitlines()), 6)  # 5 + indicator
        self.assertIn("more lines", result)

    def test_exact_limit(self):
        text = "a\nb\nc"
        result = OutputFormatter().truncate(text, 3)
        self.assertEqual(result, text)
