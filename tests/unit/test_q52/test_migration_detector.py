"""Tests for MigrationDetector — Task 352."""

from __future__ import annotations

import pytest

from lidco.analysis.migration_detector import (
    BreakingChange, BreakingKind, MigrationDetector, MigrationReport,
)


OLD_API = """\
def connect(host: str, port: int = 8080) -> bool:
    pass

def disconnect() -> None:
    pass

class Client:
    pass
"""

NEW_API_REMOVED_FN = """\
def connect(host: str, port: int = 8080) -> bool:
    pass

class Client:
    pass
"""

NEW_API_REMOVED_CLASS = """\
def connect(host: str, port: int = 8080) -> bool:
    pass

def disconnect() -> None:
    pass
"""

NEW_API_REMOVED_PARAM = """\
def connect(host: str) -> bool:
    pass

def disconnect() -> None:
    pass

class Client:
    pass
"""

NEW_API_ADDED_REQUIRED = """\
def connect(host: str, port: int, timeout: int) -> bool:
    pass

def disconnect() -> None:
    pass

class Client:
    pass
"""

NO_CHANGES = OLD_API

DEPRECATED_CODE = """\
def old_func():
    # DEPRECATED: will be removed in v2.0
    pass
"""

SYNTAX_ERROR = "def broken(:"


class TestBreakingChange:
    def test_frozen(self):
        bc = BreakingChange(kind=BreakingKind.REMOVED_FUNCTION, symbol="f", detail="x")
        with pytest.raises((AttributeError, TypeError)):
            bc.symbol = "g"  # type: ignore[misc]


class TestMigrationReport:
    def test_has_breaking_changes_true(self):
        report = MigrationReport(
            breaking_changes=[
                BreakingChange(BreakingKind.REMOVED_FUNCTION, "f", "removed")
            ]
        )
        assert report.has_breaking_changes is True

    def test_has_breaking_changes_false(self):
        report = MigrationReport()
        assert report.has_breaking_changes is False

    def test_by_kind(self):
        report = MigrationReport(
            breaking_changes=[
                BreakingChange(BreakingKind.REMOVED_FUNCTION, "f", "removed"),
                BreakingChange(BreakingKind.REMOVED_CLASS, "C", "removed"),
            ]
        )
        fns = report.by_kind(BreakingKind.REMOVED_FUNCTION)
        assert len(fns) == 1


class TestMigrationDetector:
    def setup_method(self):
        self.detector = MigrationDetector()

    def test_no_changes(self):
        report = self.detector.compare(OLD_API, NO_CHANGES)
        assert not report.has_breaking_changes

    def test_removed_function_detected(self):
        report = self.detector.compare(OLD_API, NEW_API_REMOVED_FN)
        kinds = {c.kind for c in report.breaking_changes}
        assert BreakingKind.REMOVED_FUNCTION in kinds

    def test_removed_class_detected(self):
        report = self.detector.compare(OLD_API, NEW_API_REMOVED_CLASS)
        kinds = {c.kind for c in report.breaking_changes}
        assert BreakingKind.REMOVED_CLASS in kinds

    def test_removed_param_detected(self):
        report = self.detector.compare(OLD_API, NEW_API_REMOVED_PARAM)
        kinds = {c.kind for c in report.breaking_changes}
        assert BreakingKind.REMOVED_PARAM in kinds

    def test_removed_param_symbol(self):
        report = self.detector.compare(OLD_API, NEW_API_REMOVED_PARAM)
        removed = report.by_kind(BreakingKind.REMOVED_PARAM)
        assert any(c.symbol == "connect" for c in removed)

    def test_added_required_param_detected(self):
        report = self.detector.compare(OLD_API, NEW_API_ADDED_REQUIRED)
        kinds = {c.kind for c in report.breaking_changes}
        assert BreakingKind.ADDED_REQUIRED_PARAM in kinds

    def test_syntax_error_old(self):
        report = self.detector.compare(SYNTAX_ERROR, OLD_API)
        # old is empty → all old symbols appear removed or just empty
        assert isinstance(report, MigrationReport)

    def test_syntax_error_new(self):
        report = self.detector.compare(OLD_API, SYNTAX_ERROR)
        # new is empty → all symbols "removed"
        kinds = {c.kind for c in report.breaking_changes}
        assert BreakingKind.REMOVED_FUNCTION in kinds

    def test_file_path_recorded(self):
        report = self.detector.compare(OLD_API, NEW_API_REMOVED_FN, file_path="api.py")
        assert all(c.file == "api.py" for c in report.breaking_changes)

    def test_deprecation_detected(self):
        report = self.detector.compare(OLD_API, DEPRECATED_CODE)
        assert len(report.deprecations) >= 1
