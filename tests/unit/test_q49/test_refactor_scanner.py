"""Tests for RefactorScanner — Task 341."""

from __future__ import annotations

import pytest

from lidco.analysis.refactor_scanner import RefactorCandidate, RefactorKind, RefactorScanner


# ── Source fixtures ────────────────────────────────────────────────────────────

SHORT_FN = """\
def short():
    return 1
"""

LONG_FN_TEMPLATE = "def long_fn():\n" + "    x = 1\n" * 52

MANY_ARGS_FN = """\
def many(a, b, c, d, e, f, g):
    return a + b
"""

FEW_ARGS_FN = """\
def few(a, b, c):
    return a
"""

DEEP_FN = """\
def deep():
    if True:
        for i in range(10):
            while i > 0:
                if i % 2:
                    with open("x") as f:
                        i -= 1
"""

SHALLOW_FN = """\
def shallow():
    if True:
        return 1
    return 0
"""

MAGIC_FN = """\
def magic():
    return 42
"""

NO_MAGIC_FN = """\
def no_magic():
    x = 42
    return x
"""

ALLOWED_MAGIC_FN = """\
def allowed():
    return 0 + 1 - 1 + 2
"""

SYNTAX_ERROR = "def broken(:"

METHOD_SELF = """\
class Foo:
    def method(self, a, b, c):
        return a
"""


class TestRefactorCandidate:
    def test_frozen(self):
        rc = RefactorCandidate(
            kind=RefactorKind.LONG_FUNCTION, file="x.py",
            line=1, name="f", detail="too long",
        )
        with pytest.raises((AttributeError, TypeError)):
            rc.name = "g"  # type: ignore[misc]


class TestRefactorScannerLongFunction:
    def setup_method(self):
        self.s = RefactorScanner()

    def test_short_fn_not_flagged(self):
        results = self.s.scan(SHORT_FN)
        kinds = {r.kind for r in results}
        assert RefactorKind.LONG_FUNCTION not in kinds

    def test_long_fn_flagged(self):
        results = self.s.scan(LONG_FN_TEMPLATE)
        kinds = {r.kind for r in results}
        assert RefactorKind.LONG_FUNCTION in kinds

    def test_long_fn_detail_contains_lines(self):
        results = self.s.scan(LONG_FN_TEMPLATE)
        rc = next(r for r in results if r.kind == RefactorKind.LONG_FUNCTION)
        assert "line" in rc.detail.lower() or any(c.isdigit() for c in rc.detail)


class TestRefactorScannerTooManyArgs:
    def setup_method(self):
        self.s = RefactorScanner()

    def test_few_args_not_flagged(self):
        results = self.s.scan(FEW_ARGS_FN)
        kinds = {r.kind for r in results}
        assert RefactorKind.TOO_MANY_ARGS not in kinds

    def test_many_args_flagged(self):
        results = self.s.scan(MANY_ARGS_FN)
        kinds = {r.kind for r in results}
        assert RefactorKind.TOO_MANY_ARGS in kinds

    def test_self_not_counted(self):
        # method(self, a, b, c) — only 3 real params
        results = self.s.scan(METHOD_SELF)
        kinds = {r.kind for r in results}
        assert RefactorKind.TOO_MANY_ARGS not in kinds


class TestRefactorScannerDeepNesting:
    def setup_method(self):
        self.s = RefactorScanner()

    def test_shallow_not_flagged(self):
        results = self.s.scan(SHALLOW_FN)
        kinds = {r.kind for r in results}
        assert RefactorKind.DEEP_NESTING not in kinds

    def test_deep_fn_flagged(self):
        results = self.s.scan(DEEP_FN)
        kinds = {r.kind for r in results}
        assert RefactorKind.DEEP_NESTING in kinds


class TestRefactorScannerMagicNumber:
    def setup_method(self):
        self.s = RefactorScanner()

    def test_magic_in_return_flagged(self):
        results = self.s.scan(MAGIC_FN)
        kinds = {r.kind for r in results}
        assert RefactorKind.MAGIC_NUMBER in kinds

    def test_assignment_rhs_not_flagged(self):
        # x = 42 is an assignment, should not be flagged
        results = self.s.scan(NO_MAGIC_FN)
        kinds = {r.kind for r in results}
        assert RefactorKind.MAGIC_NUMBER not in kinds

    def test_allowed_numbers_not_flagged(self):
        results = self.s.scan(ALLOWED_MAGIC_FN)
        kinds = {r.kind for r in results}
        assert RefactorKind.MAGIC_NUMBER not in kinds


class TestRefactorScannerGeneral:
    def setup_method(self):
        self.s = RefactorScanner()

    def test_syntax_error_returns_empty(self):
        assert self.s.scan(SYNTAX_ERROR) == []

    def test_empty_source_returns_empty(self):
        assert self.s.scan("") == []

    def test_file_path_recorded(self):
        results = self.s.scan(MAGIC_FN, file_path="foo.py")
        assert all(r.file == "foo.py" for r in results)

    def test_result_has_name(self):
        results = self.s.scan(MAGIC_FN)
        assert results[0].name == "magic"

    def test_result_has_line(self):
        results = self.s.scan(MAGIC_FN)
        assert results[0].line == 1

    def test_kind_enum_values(self):
        assert RefactorKind.LONG_FUNCTION.value == "long_function"
        assert RefactorKind.DEEP_NESTING.value == "deep_nesting"
        assert RefactorKind.TOO_MANY_ARGS.value == "too_many_args"
        assert RefactorKind.MAGIC_NUMBER.value == "magic_number"
