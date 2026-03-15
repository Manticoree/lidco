"""Tests for ExceptionAnalyzer — Task 355."""

from __future__ import annotations

import pytest

from lidco.analysis.exception_analyzer import (
    ExceptionAnalyzer, ExceptionIssueKind, ExceptionReport,
)


BARE_EXCEPT = """\
try:
    risky()
except:
    pass
"""

BROAD_EXCEPT = """\
try:
    risky()
except Exception:
    log_error()
"""

SWALLOWED = """\
try:
    risky()
except ValueError:
    pass
"""

GOOD_HANDLING = """\
try:
    result = parse(data)
except ValueError as e:
    raise DataError("invalid data") from e
"""

RERAISE_LOST = """\
try:
    connect()
except ConnectionError as e:
    raise RuntimeError("failed") from None
"""

MULTIPLE_ISSUES = """\
try:
    do_stuff()
except:
    pass

try:
    other_stuff()
except Exception:
    pass
"""

SYNTAX_ERROR = "def broken(:"

EMPTY_SOURCE = ""


class TestExceptionAnalyzer:
    def setup_method(self):
        self.analyzer = ExceptionAnalyzer()

    def test_empty_source(self):
        report = self.analyzer.analyze(EMPTY_SOURCE)
        assert len(report.issues) == 0

    def test_syntax_error(self):
        report = self.analyzer.analyze(SYNTAX_ERROR)
        assert isinstance(report, ExceptionReport)

    def test_good_handling_no_issues(self):
        report = self.analyzer.analyze(GOOD_HANDLING)
        bare = report.by_kind(ExceptionIssueKind.BARE_EXCEPT)
        swallowed = report.by_kind(ExceptionIssueKind.SWALLOWED_EXCEPTION)
        assert bare == []
        assert swallowed == []

    def test_bare_except_detected(self):
        report = self.analyzer.analyze(BARE_EXCEPT)
        assert report.bare_except_count >= 1

    def test_broad_except_detected(self):
        report = self.analyzer.analyze(BROAD_EXCEPT)
        broad = report.by_kind(ExceptionIssueKind.BROAD_EXCEPT)
        assert len(broad) >= 1

    def test_swallowed_exception_detected(self):
        report = self.analyzer.analyze(SWALLOWED)
        assert report.swallowed_count >= 1

    def test_bare_except_also_swallowed(self):
        # bare except with pass body is both bare AND swallowed
        report = self.analyzer.analyze(BARE_EXCEPT)
        assert report.bare_except_count >= 1
        assert report.swallowed_count >= 1

    def test_reraise_lost_detected(self):
        report = self.analyzer.analyze(RERAISE_LOST)
        lost = report.by_kind(ExceptionIssueKind.RERAISE_LOST)
        assert len(lost) >= 1

    def test_multiple_issues(self):
        report = self.analyzer.analyze(MULTIPLE_ISSUES)
        assert len(report.issues) >= 2

    def test_file_path_recorded(self):
        report = self.analyzer.analyze(BARE_EXCEPT, file_path="risky.py")
        assert all(i.file == "risky.py" for i in report.issues)

    def test_line_number_recorded(self):
        report = self.analyzer.analyze(BARE_EXCEPT)
        bare = report.by_kind(ExceptionIssueKind.BARE_EXCEPT)
        assert bare[0].line >= 1

    def test_detail_provided(self):
        report = self.analyzer.analyze(BARE_EXCEPT)
        bare = report.by_kind(ExceptionIssueKind.BARE_EXCEPT)
        assert len(bare[0].detail) > 0
