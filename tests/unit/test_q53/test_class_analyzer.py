"""Tests for ClassAnalyzer — Task 358."""

from __future__ import annotations

import pytest

from lidco.analysis.class_analyzer import (
    ClassAnalyzer, ClassIssueKind, ClassReport,
)


SIMPLE_CLASS = '''\
class Dog:
    """A dog."""

    name: str

    def bark(self) -> None:
        print("woof")
'''

DEEP_INHERITANCE = '''\
class A:
    pass

class B(A):
    pass

class Multi(A, B, object):
    pass
'''

NO_DOC_CLASS = '''\
class Widget:
    def render(self):
        pass
'''

SYNTAX_ERROR = "class Bad(:"

CLEAN_CLASS = '''\
class Point:
    """A 2D point."""
    x: float
    y: float

    def distance(self) -> float:
        return (self.x ** 2 + self.y ** 2) ** 0.5
'''


def _make_many_methods(n: int) -> str:
    body = '    """Big class."""\n'
    for i in range(n):
        body += f"\n    def method_{i}(self):\n        pass\n"
    return f"class Big:\n{body}"


def _make_god_class() -> str:
    body = '    """God class."""\n'
    for i in range(25):
        body += f"\n    def method_{i}(self):\n        pass\n"
    for i in range(10):
        body += f"\n    attr_{i}: int = 0\n"
    return f"class God:\n{body}"


class TestClassAnalyzer:
    def setup_method(self):
        self.analyzer = ClassAnalyzer()

    def test_empty_source(self):
        report = self.analyzer.analyze("")
        assert report.class_count == 0

    def test_syntax_error(self):
        report = self.analyzer.analyze(SYNTAX_ERROR)
        assert isinstance(report, ClassReport)

    def test_simple_class_info(self):
        report = self.analyzer.analyze(SIMPLE_CLASS)
        assert report.class_count == 1
        info = report.classes[0]
        assert info.name == "Dog"
        assert info.has_docstring is True

    def test_no_docstring_flagged(self):
        report = self.analyzer.analyze(NO_DOC_CLASS)
        issues = report.by_kind(ClassIssueKind.NO_DOCSTRING)
        assert len(issues) >= 1

    def test_class_with_doc_no_docstring_issue(self):
        report = self.analyzer.analyze(SIMPLE_CLASS)
        issues = report.by_kind(ClassIssueKind.NO_DOCSTRING)
        assert len(issues) == 0

    def test_deep_inheritance_detected(self):
        report = self.analyzer.analyze(DEEP_INHERITANCE)
        issues = report.by_kind(ClassIssueKind.DEEP_INHERITANCE)
        names = {i.class_name for i in issues}
        assert "Multi" in names

    def test_single_base_not_flagged(self):
        report = self.analyzer.analyze(DEEP_INHERITANCE)
        issues = report.by_kind(ClassIssueKind.DEEP_INHERITANCE)
        names = {i.class_name for i in issues}
        assert "B" not in names

    def test_too_many_methods_detected(self):
        source = _make_many_methods(22)
        report = self.analyzer.analyze(source)
        issues = report.by_kind(ClassIssueKind.TOO_MANY_METHODS)
        assert len(issues) >= 1

    def test_acceptable_method_count_not_flagged(self):
        source = _make_many_methods(5)
        report = self.analyzer.analyze(source)
        issues = report.by_kind(ClassIssueKind.TOO_MANY_METHODS)
        assert len(issues) == 0

    def test_god_class_detected(self):
        source = _make_god_class()
        report = self.analyzer.analyze(source)
        issues = report.by_kind(ClassIssueKind.GOD_CLASS)
        assert len(issues) >= 1

    def test_method_count_tracked(self):
        report = self.analyzer.analyze(SIMPLE_CLASS)
        assert report.classes[0].method_count >= 1

    def test_file_path_recorded(self):
        report = self.analyzer.analyze(SIMPLE_CLASS, file_path="pets.py")
        assert all(i.file == "pets.py" for i in report.issues)
        assert report.classes[0].file == "pets.py"

    def test_line_number_recorded(self):
        report = self.analyzer.analyze(SIMPLE_CLASS)
        assert report.classes[0].line >= 1

    def test_bases_recorded(self):
        report = self.analyzer.analyze(DEEP_INHERITANCE)
        multi = next(c for c in report.classes if c.name == "Multi")
        assert len(multi.bases) == 3

    def test_issue_detail_nonempty(self):
        report = self.analyzer.analyze(NO_DOC_CLASS)
        issues = report.by_kind(ClassIssueKind.NO_DOCSTRING)
        assert len(issues[0].detail) > 0
