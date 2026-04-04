"""Tests for lidco.multimodal.pdf_analyzer."""
from __future__ import annotations

import unittest

from lidco.multimodal.pdf_analyzer import PdfAnalyzer, TableInfo, SpecSection


class TestPdfAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = PdfAnalyzer()

    # -- extract_text -----------------------------------------------------

    def test_extract_text_default(self):
        text = self.analyzer.extract_text("doc.pdf")
        self.assertIn("Page 1", text)
        self.assertIn("doc", text)

    def test_extract_text_specific_page(self):
        text = self.analyzer.extract_text("report.pdf", pages="3")
        self.assertIn("Page 3", text)
        self.assertNotIn("Page 1", text)

    def test_extract_text_page_range(self):
        text = self.analyzer.extract_text("report.pdf", pages="2-4")
        self.assertIn("Page 2", text)
        self.assertIn("Page 4", text)

    def test_extract_text_empty_path_raises(self):
        with self.assertRaises(ValueError):
            self.analyzer.extract_text("")

    def test_extract_text_non_pdf_raises(self):
        with self.assertRaises(ValueError):
            self.analyzer.extract_text("file.txt")

    # -- extract_tables ---------------------------------------------------

    def test_extract_tables(self):
        tables = self.analyzer.extract_tables("data.pdf")
        self.assertIsInstance(tables, list)
        self.assertGreater(len(tables), 0)
        self.assertIsInstance(tables[0], TableInfo)

    def test_extract_tables_has_header(self):
        tables = self.analyzer.extract_tables("data.pdf")
        for tbl in tables:
            self.assertGreater(len(tbl.header), 0)

    def test_extract_tables_has_rows(self):
        tables = self.analyzer.extract_tables("data.pdf")
        for tbl in tables:
            self.assertGreater(len(tbl.rows), 0)

    # -- parse_spec -------------------------------------------------------

    def test_parse_spec(self):
        spec = self.analyzer.parse_spec("api_spec.pdf")
        self.assertIsInstance(spec, dict)
        self.assertIn("title", spec)
        self.assertIn("sections", spec)
        self.assertIn("page_count", spec)

    def test_parse_spec_sections(self):
        spec = self.analyzer.parse_spec("design.pdf")
        sections = spec["sections"]
        self.assertGreater(len(sections), 0)
        self.assertIn("title", sections[0])
        self.assertIn("content", sections[0])

    def test_parse_spec_title_from_filename(self):
        spec = self.analyzer.parse_spec("my_project.pdf")
        self.assertEqual(spec["title"], "My Project")

    # -- summary ----------------------------------------------------------

    def test_summary(self):
        s = self.analyzer.summary("report.pdf")
        self.assertIn("Summary", s)
        self.assertIn("Tables found", s)

    def test_summary_mentions_topics(self):
        s = self.analyzer.summary("overview.pdf")
        self.assertIn("introduction", s)

    # -- max_pages --------------------------------------------------------

    def test_max_pages_limit(self):
        analyzer = PdfAnalyzer(max_pages=3)
        text = analyzer.extract_text("big.pdf")
        self.assertIn("Page 3", text)
        self.assertNotIn("Page 4", text)

    # -- validate ---------------------------------------------------------

    def test_validate_empty_raises(self):
        with self.assertRaises(ValueError):
            self.analyzer.extract_tables("")

    def test_validate_non_pdf_raises(self):
        with self.assertRaises(ValueError):
            self.analyzer.parse_spec("readme.md")


if __name__ == "__main__":
    unittest.main()
