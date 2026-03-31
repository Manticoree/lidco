"""Tests for Q152 ErrorReportFormatter."""
from __future__ import annotations

import json
import unittest

from lidco.errors.categorizer import ErrorCategorizer
from lidco.errors.friendly_messages import FriendlyMessages
from lidco.errors.solution_suggester import SolutionSuggester
from lidco.errors.report_formatter import ErrorReportFormatter, ErrorReport


class TestErrorReport(unittest.TestCase):
    def test_fields(self):
        r = ErrorReport(
            error_type="ValueError",
            message="bad",
            category="Val",
            friendly_message="Invalid value.",
            suggestions=["fix it"],
            traceback_summary="",
            timestamp=1.0,
            context={"file": "x.py"},
        )
        self.assertEqual(r.error_type, "ValueError")
        self.assertEqual(r.category, "Val")
        self.assertEqual(r.suggestions, ["fix it"])

    def test_optional_none(self):
        r = ErrorReport("E", "m", None, None, [], "", 0.0, {})
        self.assertIsNone(r.category)
        self.assertIsNone(r.friendly_message)


class TestErrorReportFormatter(unittest.TestCase):
    def setUp(self):
        self.cat = ErrorCategorizer.with_defaults()
        self.trans = FriendlyMessages.with_defaults()
        self.sug = SolutionSuggester.with_defaults()
        self.fmt = ErrorReportFormatter(self.cat, self.trans, self.sug)

    def test_create_report_basic(self):
        try:
            raise ValueError("bad input")
        except ValueError as e:
            report = self.fmt.create_report(e)
        self.assertEqual(report.error_type, "ValueError")
        self.assertEqual(report.message, "bad input")
        self.assertIsNotNone(report.category)
        self.assertIsNotNone(report.friendly_message)

    def test_create_report_has_traceback(self):
        try:
            raise RuntimeError("test")
        except RuntimeError as e:
            report = self.fmt.create_report(e)
        self.assertIn("RuntimeError", report.traceback_summary)

    def test_create_report_with_context(self):
        report = self.fmt.create_report(RuntimeError("x"), {"file": "a.py"})
        self.assertEqual(report.context, {"file": "a.py"})

    def test_create_report_no_context(self):
        report = self.fmt.create_report(RuntimeError("x"))
        self.assertEqual(report.context, {})

    def test_create_report_timestamp(self):
        report = self.fmt.create_report(RuntimeError("x"))
        self.assertGreater(report.timestamp, 0)

    def test_create_report_suggestions_populated(self):
        report = self.fmt.create_report(FileNotFoundError("missing.txt"))
        self.assertGreater(len(report.suggestions), 0)

    def test_format_short(self):
        report = ErrorReport("ValueError", "bad", "Val", None, [], "", 0.0, {})
        out = self.fmt.format_short(report)
        self.assertIn("ValueError", out)
        self.assertIn("[Val]", out)
        self.assertIn("bad", out)

    def test_format_short_no_category(self):
        report = ErrorReport("RuntimeError", "x", None, None, [], "", 0.0, {})
        out = self.fmt.format_short(report)
        self.assertNotIn("[", out)

    def test_format_detailed(self):
        report = ErrorReport(
            "ValueError", "bad", "Val", "Invalid value.",
            ["Fix it.", "Check it."], "traceback here", 0.0, {"k": "v"}
        )
        out = self.fmt.format_detailed(report)
        self.assertIn("Error Report", out)
        self.assertIn("ValueError", out)
        self.assertIn("Val", out)
        self.assertIn("Invalid value.", out)
        self.assertIn("1. Fix it.", out)
        self.assertIn("2. Check it.", out)
        self.assertIn("traceback here", out)
        self.assertIn('"k"', out)

    def test_format_detailed_minimal(self):
        report = ErrorReport("E", "m", None, None, [], "", 0.0, {})
        out = self.fmt.format_detailed(report)
        self.assertIn("E", out)
        self.assertNotIn("Category:", out)
        self.assertNotIn("Summary:", out)

    def test_format_json(self):
        report = ErrorReport("E", "m", "C", "F", ["s"], "tb", 1.0, {"a": 1})
        out = self.fmt.format_json(report)
        data = json.loads(out)
        self.assertEqual(data["error_type"], "E")
        self.assertEqual(data["message"], "m")
        self.assertEqual(data["category"], "C")
        self.assertEqual(data["suggestions"], ["s"])
        self.assertEqual(data["context"], {"a": 1})

    def test_format_json_valid(self):
        report = ErrorReport("E", "m", None, None, [], "", 0.0, {})
        data = json.loads(self.fmt.format_json(report))
        self.assertIsNone(data["category"])


class TestFormatterWithoutComponents(unittest.TestCase):
    def test_no_categorizer(self):
        fmt = ErrorReportFormatter(translator=FriendlyMessages.with_defaults())
        report = fmt.create_report(ValueError("x"))
        self.assertIsNone(report.category)

    def test_no_translator(self):
        fmt = ErrorReportFormatter(categorizer=ErrorCategorizer.with_defaults())
        report = fmt.create_report(ValueError("x"))
        self.assertIsNone(report.friendly_message)

    def test_no_suggester(self):
        fmt = ErrorReportFormatter(categorizer=ErrorCategorizer.with_defaults())
        report = fmt.create_report(ValueError("x"))
        self.assertEqual(report.suggestions, [])

    def test_bare_formatter(self):
        fmt = ErrorReportFormatter()
        report = fmt.create_report(RuntimeError("boom"))
        self.assertEqual(report.error_type, "RuntimeError")
        self.assertIsNone(report.category)
        self.assertIsNone(report.friendly_message)
        self.assertEqual(report.suggestions, [])

    def test_context_not_mutated(self):
        fmt = ErrorReportFormatter()
        ctx = {"key": "val"}
        report = fmt.create_report(RuntimeError("x"), ctx)
        report.context["extra"] = "added"
        self.assertNotIn("extra", ctx)


if __name__ == "__main__":
    unittest.main()
