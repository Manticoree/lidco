"""Tests for visual_test/report.py — VisualTestReport."""

import json
import tempfile
import unittest
from pathlib import Path

from lidco.visual_test.report import (
    ReportConfig,
    ReportEntry,
    ReportSummary,
    VisualTestReport,
)


class TestReportEntry(unittest.TestCase):
    def test_creation(self):
        e = ReportEntry(name="home", status="pass")
        self.assertEqual(e.name, "home")
        self.assertEqual(e.status, "pass")
        self.assertEqual(e.diff_percentage, 0.0)
        self.assertEqual(e.error, "")

    def test_frozen(self):
        e = ReportEntry(name="x", status="fail")
        with self.assertRaises(AttributeError):
            e.name = "y"  # type: ignore[misc]


class TestReportSummary(unittest.TestCase):
    def test_creation(self):
        s = ReportSummary(total=10, passed=7, failed=2, new_baselines=1, errors=0)
        self.assertEqual(s.total, 10)
        self.assertEqual(s.passed, 7)


class TestReportConfig(unittest.TestCase):
    def test_defaults(self):
        c = ReportConfig()
        self.assertEqual(c.title, "Visual Regression Report")
        self.assertFalse(c.ci_mode)
        self.assertEqual(c.overlay_opacity, 0.5)

    def test_custom(self):
        c = ReportConfig(title="My Report", ci_mode=True)
        self.assertEqual(c.title, "My Report")
        self.assertTrue(c.ci_mode)


class TestVisualTestReport(unittest.TestCase):
    def test_init_default(self):
        r = VisualTestReport()
        self.assertEqual(r.entries, [])
        self.assertEqual(r.config.title, "Visual Regression Report")

    def test_add_entry(self):
        r = VisualTestReport()
        r.add_entry(ReportEntry(name="a", status="pass"))
        r.add_entry(ReportEntry(name="b", status="fail"))
        self.assertEqual(len(r.entries), 2)

    def test_add_entry_immutable(self):
        """Adding entries should not mutate previous list references."""
        r = VisualTestReport()
        before = r.entries
        r.add_entry(ReportEntry(name="a", status="pass"))
        self.assertEqual(len(before), 0)  # original unchanged
        self.assertEqual(len(r.entries), 1)

    def test_summary_empty(self):
        r = VisualTestReport()
        s = r.summary()
        self.assertEqual(s.total, 0)
        self.assertEqual(s.passed, 0)

    def test_summary_mixed(self):
        r = VisualTestReport()
        r.add_entry(ReportEntry(name="a", status="pass"))
        r.add_entry(ReportEntry(name="b", status="fail"))
        r.add_entry(ReportEntry(name="c", status="new"))
        r.add_entry(ReportEntry(name="d", status="error"))
        s = r.summary()
        self.assertEqual(s.total, 4)
        self.assertEqual(s.passed, 1)
        self.assertEqual(s.failed, 1)
        self.assertEqual(s.new_baselines, 1)
        self.assertEqual(s.errors, 1)

    def test_filter_entries(self):
        r = VisualTestReport()
        r.add_entry(ReportEntry(name="a", status="pass"))
        r.add_entry(ReportEntry(name="b", status="fail"))
        r.add_entry(ReportEntry(name="c", status="pass"))
        passed = r.filter_entries("pass")
        self.assertEqual(len(passed), 2)
        failed = r.filter_entries("fail")
        self.assertEqual(len(failed), 1)

    def test_filter_entries_none(self):
        r = VisualTestReport()
        r.add_entry(ReportEntry(name="a", status="pass"))
        all_entries = r.filter_entries(None)
        self.assertEqual(len(all_entries), 1)

    def test_generate_html(self):
        r = VisualTestReport()
        r.add_entry(ReportEntry(name="home", status="pass", diff_percentage=0.0))
        r.add_entry(ReportEntry(name="about", status="fail", diff_percentage=5.0, error="diff!"))
        html = r.generate_html()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Visual Regression Report", html)
        self.assertIn("home", html)
        self.assertIn("about", html)
        self.assertIn("diff!", html)

    def test_generate_html_custom_title(self):
        config = ReportConfig(title="Custom Title")
        r = VisualTestReport(config)
        html = r.generate_html()
        self.assertIn("Custom Title", html)

    def test_generate_html_escapes(self):
        r = VisualTestReport()
        r.add_entry(ReportEntry(name="<script>alert(1)</script>", status="pass"))
        html = r.generate_html()
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_save_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ReportConfig(output_dir=tmp)
            r = VisualTestReport(config)
            r.add_entry(ReportEntry(name="test", status="pass"))
            path = r.save_html()
            self.assertTrue(path.exists())
            content = path.read_text()
            self.assertIn("test", content)

    def test_export_json(self):
        r = VisualTestReport()
        r.add_entry(ReportEntry(name="a", status="pass", diff_percentage=0.0))
        r.add_entry(ReportEntry(name="b", status="fail", diff_percentage=3.5))
        j = r.export_json()
        data = json.loads(j)
        self.assertEqual(data["summary"]["total"], 2)
        self.assertEqual(data["summary"]["passed"], 1)
        self.assertEqual(len(data["entries"]), 2)

    def test_save_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ReportConfig(output_dir=tmp)
            r = VisualTestReport(config)
            path = r.save_json()
            self.assertTrue(path.exists())
            data = json.loads(path.read_text())
            self.assertIn("summary", data)

    def test_ci_exit_code_pass(self):
        r = VisualTestReport()
        r.add_entry(ReportEntry(name="a", status="pass"))
        r.add_entry(ReportEntry(name="b", status="new"))
        self.assertEqual(r.ci_exit_code(), 0)

    def test_ci_exit_code_fail(self):
        r = VisualTestReport()
        r.add_entry(ReportEntry(name="a", status="fail"))
        self.assertEqual(r.ci_exit_code(), 1)

    def test_ci_exit_code_error(self):
        r = VisualTestReport()
        r.add_entry(ReportEntry(name="a", status="error"))
        self.assertEqual(r.ci_exit_code(), 1)

    def test_ci_exit_code_empty(self):
        r = VisualTestReport()
        self.assertEqual(r.ci_exit_code(), 0)

    def test_save_html_custom_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ReportConfig(output_dir=tmp)
            r = VisualTestReport(config)
            path = r.save_html("custom.html")
            self.assertEqual(path.name, "custom.html")
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
