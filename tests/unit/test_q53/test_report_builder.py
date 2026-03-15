"""Tests for ReportBuilder — Task 360."""

from __future__ import annotations

import pytest
from dataclasses import dataclass
from enum import Enum

from lidco.analysis.report_builder import (
    AnalysisEntry, ReportBuilder, UnifiedReport,
)


class FakeKind(Enum):
    UNUSED = "unused"
    STAR = "star"


@dataclass(frozen=True)
class FakeIssue:
    kind: FakeKind
    file: str
    line: int
    detail: str


class FakeSeverityIssue:
    def __init__(self, kind_str: str, sev_str: str, file: str, line: int, detail: str):
        self.kind = type("K", (), {"value": kind_str})()
        self.severity = type("S", (), {"value": sev_str})()
        self.file = file
        self.line = line
        self.detail = detail


class TestReportBuilder:
    def test_empty_build(self):
        report = ReportBuilder().build()
        assert report.total == 0

    def test_add_findings_basic(self):
        issues = [FakeIssue(FakeKind.UNUSED, "a.py", 1, "Unused import")]
        report = ReportBuilder().add_findings("imports", issues).build()
        assert report.total == 1

    def test_entry_fields(self):
        issues = [FakeIssue(FakeKind.UNUSED, "a.py", 5, "Unused import os")]
        entry = ReportBuilder().add_findings("imports", issues).build().entries[0]
        assert entry.category == "imports"
        assert entry.kind == "unused"
        assert entry.file == "a.py"
        assert entry.line == 5
        assert entry.message == "Unused import os"

    def test_severity_resolved_from_category(self):
        issues = [FakeIssue(FakeKind.STAR, "a.py", 3, "Star import")]
        entry = ReportBuilder().add_findings("imports", issues).build().entries[0]
        assert entry.severity == "medium"

    def test_severity_from_attr(self):
        issues = [FakeSeverityIssue("eval_use", "critical", "x.py", 1, "eval used")]
        entry = (
            ReportBuilder()
            .add_findings("security", issues, severity_attr="severity")
            .build()
            .entries[0]
        )
        assert entry.severity == "critical"

    def test_by_severity(self):
        issues = [
            FakeIssue(FakeKind.STAR, "a.py", 1, "Star import"),
            FakeIssue(FakeKind.UNUSED, "b.py", 2, "Unused"),
        ]
        report = ReportBuilder().add_findings("imports", issues).build()
        medium = report.by_severity("medium")
        assert len(medium) >= 1

    def test_by_category(self):
        issues = [FakeIssue(FakeKind.UNUSED, "a.py", 1, "msg")]
        report = ReportBuilder().add_findings("imports", issues).build()
        assert len(report.by_category("imports")) == 1
        assert len(report.by_category("security")) == 0

    def test_by_file(self):
        issues = [
            FakeIssue(FakeKind.UNUSED, "a.py", 1, "msg"),
            FakeIssue(FakeKind.UNUSED, "b.py", 2, "msg2"),
        ]
        report = ReportBuilder().add_findings("imports", issues).build()
        assert len(report.by_file("a.py")) == 1

    def test_critical_count(self):
        issues = [FakeSeverityIssue("x", "critical", "a.py", 1, "d")]
        report = (
            ReportBuilder()
            .add_findings("security", issues, severity_attr="severity")
            .build()
        )
        assert report.critical_count == 1

    def test_high_count(self):
        issues = [FakeSeverityIssue("x", "high", "a.py", 1, "d")]
        report = (
            ReportBuilder()
            .add_findings("security", issues, severity_attr="severity")
            .build()
        )
        assert report.high_count == 1

    def test_summary_nonempty(self):
        issues = [FakeIssue(FakeKind.STAR, "a.py", 1, "msg")]
        report = ReportBuilder().add_findings("imports", issues).build()
        s = report.summary()
        assert len(s) > 0

    def test_summary_empty(self):
        report = ReportBuilder().build()
        assert report.summary() == "no issues"

    def test_metadata(self):
        report = (
            ReportBuilder()
            .set_metadata("files_scanned", 10)
            .build()
        )
        assert report.metadata["files_scanned"] == 10

    def test_chaining(self):
        i1 = [FakeIssue(FakeKind.UNUSED, "a.py", 1, "msg")]
        i2 = [FakeIssue(FakeKind.STAR, "b.py", 2, "msg2")]
        report = (
            ReportBuilder()
            .add_findings("imports", i1)
            .add_findings("imports", i2)
            .build()
        )
        assert report.total == 2

    def test_multiple_categories(self):
        i1 = [FakeIssue(FakeKind.UNUSED, "a.py", 1, "msg")]
        i2 = [FakeIssue(FakeKind.UNUSED, "a.py", 2, "msg2")]
        report = (
            ReportBuilder()
            .add_findings("imports", i1)
            .add_findings("variables", i2)
            .build()
        )
        assert len(report.by_category("imports")) == 1
        assert len(report.by_category("variables")) == 1
