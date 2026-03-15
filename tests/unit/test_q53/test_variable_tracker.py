"""Tests for VariableTracker — Task 357."""

from __future__ import annotations

import pytest

from lidco.analysis.variable_tracker import (
    VariableIssueKind, VariableReport, VariableTracker,
)


UNUSED_VAR = """\
def foo():
    x = 1
    y = 2
    return y
"""

USED_VAR = """\
def foo():
    x = 1
    return x
"""

SHADOWED = """\
def foo():
    x = 1
    x = 2
    return x
"""

GLOBAL_MISUSE = """\
COUNT = 0

def increment():
    global COUNT
    COUNT += 1
"""

CLEAN = """\
def greet(name):
    return f"Hello, {name}"
"""

SYNTAX_ERROR = "def bad(:"


class TestVariableTracker:
    def setup_method(self):
        self.tracker = VariableTracker()

    def test_empty_source(self):
        report = self.tracker.analyze("")
        assert len(report.issues) == 0

    def test_syntax_error(self):
        report = self.tracker.analyze(SYNTAX_ERROR)
        assert isinstance(report, VariableReport)

    def test_clean_no_issues(self):
        report = self.tracker.analyze(CLEAN)
        unused = report.by_kind(VariableIssueKind.UNUSED_VARIABLE)
        assert len(unused) == 0

    def test_unused_variable_detected(self):
        report = self.tracker.analyze(UNUSED_VAR)
        unused = report.by_kind(VariableIssueKind.UNUSED_VARIABLE)
        names = {i.name for i in unused}
        assert "x" in names

    def test_used_variable_not_flagged(self):
        report = self.tracker.analyze(UNUSED_VAR)
        unused = report.by_kind(VariableIssueKind.UNUSED_VARIABLE)
        names = {i.name for i in unused}
        assert "y" not in names

    def test_used_var_no_unused(self):
        report = self.tracker.analyze(USED_VAR)
        unused = report.by_kind(VariableIssueKind.UNUSED_VARIABLE)
        assert len(unused) == 0

    def test_shadowed_variable_detected(self):
        report = self.tracker.analyze(SHADOWED)
        shadowed = report.by_kind(VariableIssueKind.SHADOWED_VARIABLE)
        names = {i.name for i in shadowed}
        assert "x" in names

    def test_global_misuse_detected(self):
        report = self.tracker.analyze(GLOBAL_MISUSE)
        global_issues = report.by_kind(VariableIssueKind.GLOBAL_MISUSE)
        assert len(global_issues) >= 1

    def test_global_misuse_name(self):
        report = self.tracker.analyze(GLOBAL_MISUSE)
        global_issues = report.by_kind(VariableIssueKind.GLOBAL_MISUSE)
        assert global_issues[0].name == "COUNT"

    def test_file_path_recorded(self):
        report = self.tracker.analyze(UNUSED_VAR, file_path="myfile.py")
        assert all(i.file == "myfile.py" for i in report.issues)

    def test_line_number_recorded(self):
        report = self.tracker.analyze(UNUSED_VAR)
        unused = report.by_kind(VariableIssueKind.UNUSED_VARIABLE)
        assert unused[0].line >= 1

    def test_detail_provided(self):
        report = self.tracker.analyze(UNUSED_VAR)
        unused = report.by_kind(VariableIssueKind.UNUSED_VARIABLE)
        assert len(unused[0].detail) > 0

    def test_underscore_prefix_ignored(self):
        source = """\
def foo():
    _x = 1
    return 0
"""
        report = self.tracker.analyze(source)
        unused = report.by_kind(VariableIssueKind.UNUSED_VARIABLE)
        names = {i.name for i in unused}
        assert "_x" not in names

    def test_variables_tracked_count(self):
        report = self.tracker.analyze(UNUSED_VAR)
        assert report.variables_tracked >= 1
