"""Tests for FlowAnalyzer — Task 359."""

from __future__ import annotations

import pytest

from lidco.analysis.flow_analyzer import (
    FlowAnalyzer, FlowIssueKind, FlowReport,
)


UNREACHABLE = """\
def foo():
    return 1
    x = 2
"""

MISSING_RETURN = """\
def foo() -> int:
    x = 1
"""

INCONSISTENT = """\
def foo(x):
    if x > 0:
        return x
"""

INFINITE = """\
def loop():
    while True:
        do_work()
"""

GOOD_LOOP = """\
def loop():
    while True:
        if done():
            break
"""

CONSISTENT_RETURN = """\
def foo(x) -> int:
    if x > 0:
        return x
    return 0
"""

SYNTAX_ERROR = "def bad(:"


class TestFlowAnalyzer:
    def setup_method(self):
        self.analyzer = FlowAnalyzer()

    def test_empty_source(self):
        report = self.analyzer.analyze("")
        assert len(report.issues) == 0

    def test_syntax_error(self):
        report = self.analyzer.analyze(SYNTAX_ERROR)
        assert isinstance(report, FlowReport)

    def test_unreachable_code_detected(self):
        report = self.analyzer.analyze(UNREACHABLE)
        issues = report.by_kind(FlowIssueKind.UNREACHABLE_CODE)
        assert len(issues) >= 1

    def test_unreachable_line_number(self):
        report = self.analyzer.analyze(UNREACHABLE)
        issues = report.by_kind(FlowIssueKind.UNREACHABLE_CODE)
        assert issues[0].line >= 3

    def test_missing_return_detected(self):
        report = self.analyzer.analyze(MISSING_RETURN)
        issues = report.by_kind(FlowIssueKind.MISSING_RETURN)
        assert len(issues) >= 1

    def test_inconsistent_return_detected(self):
        report = self.analyzer.analyze(INCONSISTENT)
        issues = report.by_kind(FlowIssueKind.INCONSISTENT_RETURN)
        assert len(issues) >= 1

    def test_consistent_return_no_issue(self):
        report = self.analyzer.analyze(CONSISTENT_RETURN)
        missing = report.by_kind(FlowIssueKind.MISSING_RETURN)
        incons = report.by_kind(FlowIssueKind.INCONSISTENT_RETURN)
        assert len(missing) == 0
        assert len(incons) == 0

    def test_infinite_loop_detected(self):
        report = self.analyzer.analyze(INFINITE)
        issues = report.by_kind(FlowIssueKind.INFINITE_LOOP)
        assert len(issues) >= 1

    def test_loop_with_break_not_flagged(self):
        report = self.analyzer.analyze(GOOD_LOOP)
        issues = report.by_kind(FlowIssueKind.INFINITE_LOOP)
        assert len(issues) == 0

    def test_functions_analyzed_count(self):
        report = self.analyzer.analyze(UNREACHABLE)
        assert report.functions_analyzed >= 1

    def test_file_path_recorded(self):
        report = self.analyzer.analyze(UNREACHABLE, file_path="app.py")
        assert all(i.file == "app.py" for i in report.issues)

    def test_function_name_recorded(self):
        report = self.analyzer.analyze(UNREACHABLE)
        issues = report.by_kind(FlowIssueKind.UNREACHABLE_CODE)
        assert issues[0].function == "foo"

    def test_detail_nonempty(self):
        report = self.analyzer.analyze(UNREACHABLE)
        issues = report.by_kind(FlowIssueKind.UNREACHABLE_CODE)
        assert len(issues[0].detail) > 0
