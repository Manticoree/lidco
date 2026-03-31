"""Tests for Q139 ReportRenderer."""
from __future__ import annotations

import unittest

from lidco.ui.report_renderer import ReportRenderer, ReportSection


class TestReportSection(unittest.TestCase):
    def test_defaults(self):
        rs = ReportSection(title="T", content="C")
        self.assertEqual(rs.level, 1)

    def test_custom_level(self):
        rs = ReportSection(title="T", content="C", level=3)
        self.assertEqual(rs.level, 3)


class TestReportRendererInit(unittest.TestCase):
    def test_title(self):
        rr = ReportRenderer("My Report")
        self.assertEqual(rr._title, "My Report")

    def test_empty_entries(self):
        rr = ReportRenderer("R")
        self.assertEqual(len(rr._entries), 0)


class TestAddSection(unittest.TestCase):
    def test_add_section(self):
        rr = ReportRenderer("R")
        rr.add_section("S1", "content")
        self.assertEqual(len(rr._entries), 1)

    def test_add_section_with_level(self):
        rr = ReportRenderer("R")
        rr.add_section("S1", "c", level=2)
        entry = rr._entries[0]
        self.assertIsInstance(entry, ReportSection)
        self.assertEqual(entry.level, 2)


class TestAddKeyValue(unittest.TestCase):
    def test_add_key_value(self):
        rr = ReportRenderer("R")
        rr.add_key_value("Version", "1.0")
        self.assertEqual(len(rr._entries), 1)


class TestAddList(unittest.TestCase):
    def test_add_list(self):
        rr = ReportRenderer("R")
        rr.add_list(["a", "b", "c"])
        self.assertEqual(len(rr._entries), 1)


class TestAddDivider(unittest.TestCase):
    def test_add_divider(self):
        rr = ReportRenderer("R")
        rr.add_divider()
        self.assertEqual(len(rr._entries), 1)


class TestSummary(unittest.TestCase):
    def test_summary_no_sections(self):
        rr = ReportRenderer("Report")
        result = rr.summary()
        self.assertIn("Report", result)
        self.assertIn("0 sections", result)

    def test_summary_with_sections(self):
        rr = ReportRenderer("Report")
        rr.add_section("S1", "c")
        rr.add_section("S2", "c")
        rr.add_key_value("k", "v")  # not a section
        result = rr.summary()
        self.assertIn("2 sections", result)


class TestRenderPlainText(unittest.TestCase):
    def test_render_title(self):
        rr = ReportRenderer("My Report")
        result = rr.render()
        self.assertIn("=== My Report ===", result)

    def test_render_section(self):
        rr = ReportRenderer("R")
        rr.add_section("Overview", "Some text")
        result = rr.render()
        self.assertIn("--- Overview ---", result)
        self.assertIn("Some text", result)

    def test_render_key_value(self):
        rr = ReportRenderer("R")
        rr.add_key_value("Version", "2.0")
        result = rr.render()
        self.assertIn("Version: 2.0", result)

    def test_render_list(self):
        rr = ReportRenderer("R")
        rr.add_list(["alpha", "beta"])
        result = rr.render()
        self.assertIn("- alpha", result)
        self.assertIn("- beta", result)

    def test_render_divider(self):
        rr = ReportRenderer("R")
        rr.add_divider()
        result = rr.render()
        self.assertIn("---", result)

    def test_render_nested_section(self):
        rr = ReportRenderer("R")
        rr.add_section("Deep", "content", level=2)
        result = rr.render()
        self.assertIn("Deep", result)
        self.assertIn("content", result)


class TestRenderMarkdown(unittest.TestCase):
    def test_markdown_title(self):
        rr = ReportRenderer("My Report")
        result = rr.render_markdown()
        self.assertIn("# My Report", result)

    def test_markdown_section(self):
        rr = ReportRenderer("R")
        rr.add_section("Overview", "Text")
        result = rr.render_markdown()
        self.assertIn("## Overview", result)
        self.assertIn("Text", result)

    def test_markdown_section_level(self):
        rr = ReportRenderer("R")
        rr.add_section("Deep", "c", level=3)
        result = rr.render_markdown()
        self.assertIn("#### Deep", result)

    def test_markdown_key_value(self):
        rr = ReportRenderer("R")
        rr.add_key_value("Key", "Val")
        result = rr.render_markdown()
        self.assertIn("**Key:** Val", result)

    def test_markdown_list(self):
        rr = ReportRenderer("R")
        rr.add_list(["one", "two"])
        result = rr.render_markdown()
        self.assertIn("- one", result)
        self.assertIn("- two", result)

    def test_markdown_divider(self):
        rr = ReportRenderer("R")
        rr.add_divider()
        result = rr.render_markdown()
        self.assertIn("---", result)


if __name__ == "__main__":
    unittest.main()
