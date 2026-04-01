"""Tests for TechDebtTracker, DebtItem, DebtReport."""
from __future__ import annotations

import os
import tempfile
import unittest

from lidco.project_analytics.debt_tracker import (
    DebtItem,
    DebtReport,
    TechDebtTracker,
)


class TestDebtItem(unittest.TestCase):
    def test_frozen(self):
        item = DebtItem(file="a.py", line=1, marker="TODO", text="do it")
        with self.assertRaises(AttributeError):
            item.file = "b.py"  # type: ignore[misc]

    def test_defaults(self):
        item = DebtItem(file="x.py", line=5, marker="FIXME", text="fix")
        self.assertEqual(item.severity, "medium")
        self.assertAlmostEqual(item.estimated_hours, 0.5)


class TestDebtReport(unittest.TestCase):
    def test_defaults(self):
        report = DebtReport()
        self.assertEqual(report.items, ())
        self.assertEqual(report.total_hours, 0.0)
        self.assertEqual(report.by_severity, {})


class TestTechDebtTracker(unittest.TestCase):
    def test_scan_text_finds_todo(self):
        tracker = TechDebtTracker()
        items = tracker.scan_text("# TODO: fix this\npass\n")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].marker, "TODO")
        self.assertEqual(items[0].line, 1)

    def test_scan_text_multiple_markers(self):
        tracker = TechDebtTracker()
        text = "# TODO: a\n# FIXME: b\n# HACK: c\n# XXX: d\n"
        items = tracker.scan_text(text)
        self.assertEqual(len(items), 4)
        markers = {i.marker for i in items}
        self.assertEqual(markers, {"TODO", "FIXME", "HACK", "XXX"})

    def test_scan_text_custom_markers(self):
        tracker = TechDebtTracker(markers=["WARN"])
        items = tracker.scan_text("# WARN: attention\n# TODO: ignored\n")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].marker, "WARN")

    def test_scan_file(self):
        tracker = TechDebtTracker()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write("# TODO: test item\ncode()\n# FIXME: another\n")
            path = f.name
        try:
            items = tracker.scan_file(path)
            self.assertEqual(len(items), 2)
        finally:
            os.unlink(path)

    def test_add_item_and_report(self):
        tracker = TechDebtTracker()
        item = DebtItem(file="a.py", line=1, marker="TODO", text="t", estimated_hours=2.0)
        tracker.add_item(item)
        report = tracker.report()
        self.assertEqual(len(report.items), 1)
        self.assertAlmostEqual(report.total_hours, 2.0)

    def test_by_file(self):
        tracker = TechDebtTracker()
        tracker.add_item(DebtItem(file="a.py", line=1, marker="TODO", text="x"))
        tracker.add_item(DebtItem(file="b.py", line=2, marker="FIXME", text="y"))
        tracker.add_item(DebtItem(file="a.py", line=3, marker="HACK", text="z"))
        grouped = tracker.by_file()
        self.assertEqual(len(grouped["a.py"]), 2)
        self.assertEqual(len(grouped["b.py"]), 1)

    def test_clear(self):
        tracker = TechDebtTracker()
        tracker.add_item(DebtItem(file="a.py", line=1, marker="TODO", text="x"))
        tracker.clear()
        report = tracker.report()
        self.assertEqual(len(report.items), 0)

    def test_severity_mapping(self):
        tracker = TechDebtTracker()
        items = tracker.scan_text("# TODO: low\n# FIXME: high\n# HACK: med\n# XXX: high\n")
        severities = {i.marker: i.severity for i in items}
        self.assertEqual(severities["TODO"], "low")
        self.assertEqual(severities["FIXME"], "high")
        self.assertEqual(severities["HACK"], "medium")
        self.assertEqual(severities["XXX"], "high")
