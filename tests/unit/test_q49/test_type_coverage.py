"""Tests for TypeCoverageChecker — Task 340."""

from __future__ import annotations

import pytest

from lidco.analysis.type_coverage import TypeCoverageChecker, TypeCoverageResult


NO_ANNOTATIONS = """\
def add(a, b):
    return a + b
"""

FULL_ANNOTATIONS = """\
def add(a: int, b: int) -> int:
    return a + b
"""

PARTIAL_ANNOTATIONS = """\
def process(x: int, y) -> None:
    pass
"""

METHOD_WITH_SELF = """\
class Foo:
    def method(self, x: int) -> str:
        return str(x)
"""

VARARG_FN = """\
def variadic(*args: int, **kwargs: str) -> None:
    pass
"""

EMPTY_SOURCE = ""

SYNTAX_ERROR = "def broken(:"


class TestTypeCoverageResult:
    def test_frozen(self):
        r = TypeCoverageResult(
            file="x.py",
            annotated_params=1,
            total_params=2,
            annotated_returns=1,
            total_functions=1,
        )
        with pytest.raises((AttributeError, TypeError)):
            r.annotated_params = 5  # type: ignore[misc]

    def test_coverage_property(self):
        r = TypeCoverageResult(
            file="x.py",
            annotated_params=2,
            total_params=2,
            annotated_returns=1,
            total_functions=1,
        )
        # (2 params + 1 return) / (2 params + 1 function) = 3/3 = 1.0
        assert r.coverage == pytest.approx(1.0)

    def test_coverage_zero_functions(self):
        r = TypeCoverageResult(file="x.py", annotated_params=0,
                               total_params=0, annotated_returns=0, total_functions=0)
        assert r.coverage == 1.0

    def test_coverage_partial(self):
        r = TypeCoverageResult(file="x.py", annotated_params=1,
                               total_params=2, annotated_returns=0, total_functions=1)
        # 1 / (2 + 1) = 1/3
        assert r.coverage == pytest.approx(1 / 3)


class TestTypeCoverageChecker:
    def setup_method(self):
        self.checker = TypeCoverageChecker()

    def test_empty_source(self):
        result = self.checker.check_source(EMPTY_SOURCE)
        assert result.total_functions == 0
        assert result.coverage == 1.0

    def test_syntax_error(self):
        result = self.checker.check_source(SYNTAX_ERROR)
        assert result.total_functions == 0

    def test_no_annotations(self):
        result = self.checker.check_source(NO_ANNOTATIONS)
        assert result.total_functions == 1
        assert result.annotated_params == 0
        assert result.annotated_returns == 0
        assert result.total_params == 2

    def test_full_annotations(self):
        result = self.checker.check_source(FULL_ANNOTATIONS)
        assert result.total_functions == 1
        assert result.annotated_params == 2
        assert result.total_params == 2
        assert result.annotated_returns == 1
        assert result.coverage == pytest.approx(1.0)

    def test_partial_annotations(self):
        result = self.checker.check_source(PARTIAL_ANNOTATIONS)
        # x is annotated, y is not; return is annotated
        assert result.annotated_params == 1
        assert result.total_params == 2
        assert result.annotated_returns == 1

    def test_self_excluded(self):
        result = self.checker.check_source(METHOD_WITH_SELF)
        # self should not count; only x counts as param
        assert result.total_params == 1
        assert result.annotated_params == 1

    def test_varargs_counted(self):
        result = self.checker.check_source(VARARG_FN)
        # *args + **kwargs = 2 params, both annotated
        assert result.total_params == 2
        assert result.annotated_params == 2

    def test_file_path_recorded(self):
        result = self.checker.check_source(FULL_ANNOTATIONS, file_path="a.py")
        assert result.file == "a.py"

    def test_multiple_functions(self):
        src = NO_ANNOTATIONS + "\n" + FULL_ANNOTATIONS
        result = self.checker.check_source(src)
        assert result.total_functions == 2
