"""Tests for DocCoverageChecker — Task 346."""

from __future__ import annotations

import pytest

from lidco.analysis.doc_coverage import DocCoverageChecker, DocCoverageResult


ALL_DOCUMENTED = '''\
def foo():
    """Docstring."""
    pass

class Bar:
    """Class docstring."""

    def method(self):
        """Method docstring."""
        pass
'''

NONE_DOCUMENTED = '''\
def foo():
    pass

class Bar:
    def method(self):
        pass
'''

PARTIAL = '''\
def documented():
    """Has docs."""
    pass

def undocumented():
    pass
'''

EMPTY_SOURCE = ""

SYNTAX_ERROR = "def broken(:"


class TestDocCoverageResult:
    def test_frozen(self):
        r = DocCoverageResult(
            file="x.py",
            documented_functions=1,
            total_functions=2,
            documented_classes=0,
            total_classes=1,
        )
        with pytest.raises((AttributeError, TypeError)):
            r.documented_functions = 2  # type: ignore[misc]

    def test_function_coverage(self):
        r = DocCoverageResult(
            file="x.py", documented_functions=1, total_functions=2,
            documented_classes=0, total_classes=0,
        )
        assert r.function_coverage == pytest.approx(0.5)

    def test_class_coverage(self):
        r = DocCoverageResult(
            file="x.py", documented_functions=0, total_functions=0,
            documented_classes=1, total_classes=2,
        )
        assert r.class_coverage == pytest.approx(0.5)

    def test_overall_coverage(self):
        r = DocCoverageResult(
            file="x.py", documented_functions=1, total_functions=2,
            documented_classes=1, total_classes=2,
        )
        # 2/4 = 0.5
        assert r.overall_coverage == pytest.approx(0.5)

    def test_no_functions_coverage_is_1(self):
        r = DocCoverageResult(
            file="x.py", documented_functions=0, total_functions=0,
            documented_classes=0, total_classes=0,
        )
        assert r.function_coverage == 1.0
        assert r.class_coverage == 1.0
        assert r.overall_coverage == 1.0


class TestDocCoverageChecker:
    def setup_method(self):
        self.checker = DocCoverageChecker()

    def test_empty_source(self):
        r = self.checker.check_source(EMPTY_SOURCE)
        assert r.total_functions == 0
        assert r.overall_coverage == 1.0

    def test_syntax_error(self):
        r = self.checker.check_source(SYNTAX_ERROR)
        assert r.total_functions == 0

    def test_all_documented(self):
        r = self.checker.check_source(ALL_DOCUMENTED)
        assert r.function_coverage == pytest.approx(1.0)
        assert r.class_coverage == pytest.approx(1.0)

    def test_none_documented(self):
        r = self.checker.check_source(NONE_DOCUMENTED)
        assert r.function_coverage == pytest.approx(0.0)
        assert r.class_coverage == pytest.approx(0.0)

    def test_partial_documentation(self):
        r = self.checker.check_source(PARTIAL)
        assert r.total_functions == 2
        assert r.documented_functions == 1
        assert r.function_coverage == pytest.approx(0.5)

    def test_counts_methods(self):
        r = self.checker.check_source(ALL_DOCUMENTED)
        # foo + method = 2 functions; Bar = 1 class
        assert r.total_functions == 2
        assert r.total_classes == 1

    def test_file_path_recorded(self):
        r = self.checker.check_source(PARTIAL, file_path="myfile.py")
        assert r.file == "myfile.py"
