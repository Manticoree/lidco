"""Tests for LintRunner — Task 342."""

from __future__ import annotations

import pytest

from lidco.analysis.lint_runner import LintIssue, LintReport, LintRunner, Severity


RUFF_OUTPUT = """\
src/foo.py:10:5: E501 Line too long (92 > 88 characters)
src/foo.py:15:1: F401 `os` imported but unused
src/bar.py:3:1: W291 Trailing whitespace
"""

MYPY_OUTPUT = """\
src/foo.py:10: error: Argument 1 to "foo" has incompatible type [arg-type]
src/foo.py:20: warning: Returning Any from function declared to return "int"
src/bar.py:5: note: Revealed type is 'builtins.int'
"""

EMPTY_OUTPUT = ""


class TestLintIssue:
    def test_frozen(self):
        issue = LintIssue(file="a.py", line=1, col=0, code="E501", message="too long")
        with pytest.raises((AttributeError, TypeError)):
            issue.line = 2  # type: ignore[misc]

    def test_default_severity(self):
        issue = LintIssue(file="a.py", line=1, col=0, code="E501", message="x")
        assert issue.severity == Severity.WARNING


class TestLintReport:
    def test_error_count(self):
        issues = [
            LintIssue("a.py", 1, 0, "E501", "x", Severity.ERROR),
            LintIssue("a.py", 2, 0, "W291", "y", Severity.WARNING),
        ]
        report = LintReport(issues=issues)
        assert report.error_count == 1
        assert report.warning_count == 1

    def test_total(self):
        report = LintReport(issues=[
            LintIssue("a.py", 1, 0, "E1", "x", Severity.ERROR),
            LintIssue("b.py", 2, 0, "W1", "y", Severity.WARNING),
        ])
        assert report.total == 2

    def test_empty_report(self):
        report = LintReport()
        assert report.total == 0
        assert report.error_count == 0

    def test_by_file(self):
        issues = [
            LintIssue("a.py", 1, 0, "E1", "x"),
            LintIssue("a.py", 2, 0, "E2", "y"),
            LintIssue("b.py", 3, 0, "W1", "z"),
        ]
        report = LintReport(issues=issues)
        by_file = report.by_file()
        assert len(by_file["a.py"]) == 2
        assert len(by_file["b.py"]) == 1

    def test_filter_severity(self):
        issues = [
            LintIssue("a.py", 1, 0, "E1", "x", Severity.ERROR),
            LintIssue("a.py", 2, 0, "W1", "y", Severity.WARNING),
        ]
        report = LintReport(issues=issues)
        errors = report.filter_severity(Severity.ERROR)
        assert len(errors) == 1
        assert errors[0].code == "E1"


class TestLintRunnerRuff:
    def setup_method(self):
        self.runner = LintRunner()

    def test_empty_returns_empty(self):
        result = self.runner.parse_ruff(EMPTY_OUTPUT)
        assert result.total == 0

    def test_parses_issues(self):
        result = self.runner.parse_ruff(RUFF_OUTPUT)
        assert result.total == 3

    def test_file_path_extracted(self):
        result = self.runner.parse_ruff(RUFF_OUTPUT)
        files = {i.file for i in result.issues}
        assert "src/foo.py" in files
        assert "src/bar.py" in files

    def test_line_and_col_extracted(self):
        result = self.runner.parse_ruff(RUFF_OUTPUT)
        issue = next(i for i in result.issues if i.code == "E501")
        assert issue.line == 10
        assert issue.col == 5

    def test_code_extracted(self):
        result = self.runner.parse_ruff(RUFF_OUTPUT)
        codes = {i.code for i in result.issues}
        assert "E501" in codes
        assert "F401" in codes

    def test_e_and_f_codes_are_errors(self):
        result = self.runner.parse_ruff(RUFF_OUTPUT)
        e501 = next(i for i in result.issues if i.code == "E501")
        f401 = next(i for i in result.issues if i.code == "F401")
        assert e501.severity == Severity.ERROR
        assert f401.severity == Severity.ERROR

    def test_w_codes_are_warnings(self):
        result = self.runner.parse_ruff(RUFF_OUTPUT)
        w291 = next(i for i in result.issues if i.code == "W291")
        assert w291.severity == Severity.WARNING


class TestLintRunnerMypy:
    def setup_method(self):
        self.runner = LintRunner()

    def test_empty_returns_empty(self):
        result = self.runner.parse_mypy(EMPTY_OUTPUT)
        assert result.total == 0

    def test_parses_errors(self):
        result = self.runner.parse_mypy(MYPY_OUTPUT)
        errors = [i for i in result.issues if i.severity == Severity.ERROR]
        assert len(errors) == 1

    def test_parses_warnings(self):
        result = self.runner.parse_mypy(MYPY_OUTPUT)
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1

    def test_note_is_info(self):
        result = self.runner.parse_mypy(MYPY_OUTPUT)
        notes = [i for i in result.issues if i.severity == Severity.INFO]
        assert len(notes) == 1

    def test_line_number_extracted(self):
        result = self.runner.parse_mypy(MYPY_OUTPUT)
        err = next(i for i in result.issues if i.severity == Severity.ERROR)
        assert err.line == 10


class TestLintRunnerMerge:
    def setup_method(self):
        self.runner = LintRunner()

    def test_merge_combines_issues(self):
        r1 = self.runner.parse_ruff(RUFF_OUTPUT)
        r2 = self.runner.parse_mypy(MYPY_OUTPUT)
        merged = self.runner.merge(r1, r2)
        assert merged.total == r1.total + r2.total

    def test_merge_deduplicates(self):
        r1 = self.runner.parse_ruff(RUFF_OUTPUT)
        merged = self.runner.merge(r1, r1)
        assert merged.total == r1.total  # no duplicates
