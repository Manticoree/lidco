"""Tests for Q139 TableFormatter."""
from __future__ import annotations

import unittest

from lidco.ui.table_formatter import Column, TableFormatter


class TestColumn(unittest.TestCase):
    def test_defaults(self):
        col = Column(name="Test")
        self.assertIsNone(col.width)
        self.assertEqual(col.align, "left")
        self.assertEqual(col.min_width, 3)

    def test_custom(self):
        col = Column(name="X", width=20, align="right", min_width=5)
        self.assertEqual(col.width, 20)
        self.assertEqual(col.align, "right")
        self.assertEqual(col.min_width, 5)


class TestTableFormatterInit(unittest.TestCase):
    def test_string_columns(self):
        tf = TableFormatter(["A", "B"])
        self.assertEqual(len(tf._columns), 2)
        self.assertEqual(tf._columns[0].name, "A")

    def test_column_objects(self):
        tf = TableFormatter([Column(name="X", width=10)])
        self.assertEqual(tf._columns[0].width, 10)

    def test_mixed_columns(self):
        tf = TableFormatter(["A", Column(name="B")])
        self.assertEqual(len(tf._columns), 2)


class TestTableFormatterRows(unittest.TestCase):
    def test_add_row(self):
        tf = TableFormatter(["A", "B"])
        tf.add_row("1", "2")
        self.assertEqual(tf.row_count, 1)

    def test_add_multiple_rows(self):
        tf = TableFormatter(["A"])
        tf.add_row("x")
        tf.add_row("y")
        tf.add_row("z")
        self.assertEqual(tf.row_count, 3)

    def test_row_padding(self):
        tf = TableFormatter(["A", "B", "C"])
        tf.add_row("only_one")
        self.assertEqual(tf.row_count, 1)

    def test_row_truncation(self):
        tf = TableFormatter(["A"])
        tf.add_row("x", "y", "z")
        self.assertEqual(tf.row_count, 1)

    def test_add_separator(self):
        tf = TableFormatter(["A"])
        tf.add_row("x")
        tf.add_separator()
        tf.add_row("y")
        self.assertEqual(tf.row_count, 2)  # separators not counted

    def test_clear(self):
        tf = TableFormatter(["A"])
        tf.add_row("1")
        tf.add_row("2")
        tf.clear()
        self.assertEqual(tf.row_count, 0)


class TestTableFormatterRender(unittest.TestCase):
    def test_render_has_borders(self):
        tf = TableFormatter(["Name", "Value"])
        tf.add_row("a", "1")
        result = tf.render()
        self.assertIn("+", result)
        self.assertIn("|", result)
        self.assertIn("-", result)

    def test_render_contains_header(self):
        tf = TableFormatter(["Name"])
        result = tf.render()
        self.assertIn("Name", result)

    def test_render_contains_data(self):
        tf = TableFormatter(["Col"])
        tf.add_row("value123")
        result = tf.render()
        self.assertIn("value123", result)

    def test_render_separator_row(self):
        tf = TableFormatter(["A"])
        tf.add_row("x")
        tf.add_separator()
        tf.add_row("y")
        result = tf.render()
        lines = result.split("\n")
        # Should have multiple horizontal lines (header top, header bottom, separator, footer)
        hlines = [l for l in lines if l.startswith("+")]
        self.assertGreaterEqual(len(hlines), 4)

    def test_render_empty_table(self):
        tf = TableFormatter(["A", "B"])
        result = tf.render()
        self.assertIn("A", result)
        self.assertIn("B", result)

    def test_render_right_align(self):
        tf = TableFormatter([Column(name="Num", align="right")])
        tf.add_row("42")
        result = tf.render()
        self.assertIn("42", result)

    def test_render_center_align(self):
        tf = TableFormatter([Column(name="Mid", align="center")])
        tf.add_row("x")
        result = tf.render()
        self.assertIn("x", result)


class TestTableFormatterCompact(unittest.TestCase):
    def test_compact_no_borders(self):
        tf = TableFormatter(["A", "B"])
        tf.add_row("1", "2")
        result = tf.render_compact()
        self.assertNotIn("+", result)
        self.assertNotIn("|", result)

    def test_compact_has_header(self):
        tf = TableFormatter(["Name"])
        result = tf.render_compact()
        self.assertIn("Name", result)

    def test_compact_skips_separators(self):
        tf = TableFormatter(["A"])
        tf.add_row("x")
        tf.add_separator()
        tf.add_row("y")
        result = tf.render_compact()
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 3)  # header + 2 data


class TestTableFormatterMarkdown(unittest.TestCase):
    def test_markdown_pipe_format(self):
        tf = TableFormatter(["Name", "Value"])
        tf.add_row("a", "1")
        result = tf.render_markdown()
        lines = result.split("\n")
        self.assertTrue(lines[0].startswith("|"))
        self.assertIn("---", lines[1])

    def test_markdown_right_align_colon(self):
        tf = TableFormatter([Column(name="N", align="right")])
        tf.add_row("1")
        result = tf.render_markdown()
        lines = result.split("\n")
        self.assertIn(":", lines[1])

    def test_markdown_center_align(self):
        tf = TableFormatter([Column(name="N", align="center")])
        tf.add_row("1")
        result = tf.render_markdown()
        lines = result.split("\n")
        sep = lines[1]
        self.assertTrue(sep.count(":") >= 1)

    def test_markdown_skips_separators(self):
        tf = TableFormatter(["A"])
        tf.add_row("x")
        tf.add_separator()
        tf.add_row("y")
        result = tf.render_markdown()
        lines = [l for l in result.split("\n") if l.strip()]
        # header + sep + 2 data = 4
        self.assertEqual(len(lines), 4)


class TestAutoWidth(unittest.TestCase):
    def test_auto_width_from_content(self):
        tf = TableFormatter(["X"])
        tf.add_row("a_very_long_value")
        widths = tf._effective_widths()
        self.assertGreaterEqual(widths[0], len("a_very_long_value"))

    def test_fixed_width_column(self):
        tf = TableFormatter([Column(name="A", width=15)])
        tf.add_row("short")
        widths = tf._effective_widths()
        self.assertEqual(widths[0], 15)

    def test_min_width_respected(self):
        tf = TableFormatter([Column(name="X", min_width=10)])
        widths = tf._effective_widths()
        self.assertGreaterEqual(widths[0], 10)


if __name__ == "__main__":
    unittest.main()
