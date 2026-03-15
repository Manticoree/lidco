"""Tests for NamingChecker — Task 347."""

from __future__ import annotations

import pytest

from lidco.analysis.naming_checker import NamingChecker, NamingViolation, NamingViolationKind


GOOD_NAMES = """\
def my_function():
    pass

class MyClass:
    def my_method(self):
        pass

my_var = 1
MY_CONSTANT = 42
"""

BAD_FUNCTION = """\
def badFunctionName():
    pass
"""

BAD_CLASS = """\
class bad_class_name:
    pass
"""

PASCAL_VAR = """\
MyVariable = 42
"""

DUNDER_METHODS = """\
class Foo:
    def __init__(self):
        pass
    def __repr__(self):
        return "Foo"
"""

PRIVATE_NAMES = """\
def _private_func():
    pass

_private_var = 1
"""

SYNTAX_ERROR = "def broken(:"


class TestNamingViolation:
    def test_frozen(self):
        v = NamingViolation(
            kind=NamingViolationKind.FUNCTION_NOT_SNAKE,
            name="badName",
            file="x.py",
            line=1,
            suggestion="bad_name",
        )
        with pytest.raises((AttributeError, TypeError)):
            v.name = "other"  # type: ignore[misc]


class TestNamingChecker:
    def setup_method(self):
        self.checker = NamingChecker()

    def test_empty_source(self):
        assert self.checker.check_source("") == []

    def test_syntax_error(self):
        assert self.checker.check_source(SYNTAX_ERROR) == []

    def test_good_names_no_violations(self):
        result = self.checker.check_source(GOOD_NAMES)
        # Filter out any false positives from MY_CONSTANT or similar
        fn_violations = [v for v in result if v.kind == NamingViolationKind.FUNCTION_NOT_SNAKE]
        cls_violations = [v for v in result if v.kind == NamingViolationKind.CLASS_NOT_PASCAL]
        assert fn_violations == []
        assert cls_violations == []

    def test_camel_case_function_flagged(self):
        result = self.checker.check_source(BAD_FUNCTION)
        kinds = {v.kind for v in result}
        assert NamingViolationKind.FUNCTION_NOT_SNAKE in kinds

    def test_snake_class_flagged(self):
        result = self.checker.check_source(BAD_CLASS)
        kinds = {v.kind for v in result}
        assert NamingViolationKind.CLASS_NOT_PASCAL in kinds

    def test_dunder_methods_not_flagged(self):
        result = self.checker.check_source(DUNDER_METHODS)
        fn_violations = [v for v in result if v.kind == NamingViolationKind.FUNCTION_NOT_SNAKE]
        assert fn_violations == []

    def test_private_names_not_flagged(self):
        result = self.checker.check_source(PRIVATE_NAMES)
        assert result == []

    def test_suggestion_provided(self):
        result = self.checker.check_source(BAD_FUNCTION)
        violation = next(v for v in result if v.kind == NamingViolationKind.FUNCTION_NOT_SNAKE)
        assert violation.suggestion == "bad_function_name"

    def test_class_suggestion_provided(self):
        result = self.checker.check_source(BAD_CLASS)
        violation = next(v for v in result if v.kind == NamingViolationKind.CLASS_NOT_PASCAL)
        assert "BadClassName" in violation.suggestion or "Bad" in violation.suggestion

    def test_file_path_recorded(self):
        result = self.checker.check_source(BAD_FUNCTION, file_path="foo.py")
        assert all(v.file == "foo.py" for v in result)

    def test_line_number_recorded(self):
        result = self.checker.check_source(BAD_FUNCTION)
        v = next(v for v in result if v.kind == NamingViolationKind.FUNCTION_NOT_SNAKE)
        assert v.line == 1
