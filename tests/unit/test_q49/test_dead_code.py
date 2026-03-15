"""Tests for DeadCodeDetector — Task 339."""

from __future__ import annotations

import pytest

from lidco.analysis.dead_code import DeadCodeDetector, DeadSymbol


USED_FN = """\
def helper():
    return 42

result = helper()
"""

DEAD_FN = """\
def unused_function():
    return 99

x = 1
"""

DEAD_IMPORT = """\
import os
import sys

print(sys.version)
"""

DEAD_CLASS = """\
class Unused:
    pass

active = 1
"""

STAR_IMPORT = """\
from module import *

def foo():
    return bar()
"""

SYNTAX_ERROR = "def broken(:"


class TestDeadSymbol:
    def test_frozen(self):
        ds = DeadSymbol(name="f", kind="function", file="x.py", line=1)
        with pytest.raises((AttributeError, TypeError)):
            ds.name = "g"  # type: ignore[misc]


class TestDeadCodeDetector:
    def setup_method(self):
        self.dcd = DeadCodeDetector()

    def test_empty_source(self):
        assert self.dcd.scan_file("") == []

    def test_syntax_error_returns_empty(self):
        assert self.dcd.scan_file(SYNTAX_ERROR) == []

    def test_star_import_returns_empty(self):
        assert self.dcd.scan_file(STAR_IMPORT) == []

    def test_used_function_not_flagged(self):
        result = self.dcd.scan_file(USED_FN)
        names = {s.name for s in result}
        assert "helper" not in names

    def test_dead_function_flagged(self):
        result = self.dcd.scan_file(DEAD_FN)
        names = {s.name for s in result}
        assert "unused_function" in names

    def test_dead_function_kind(self):
        result = self.dcd.scan_file(DEAD_FN)
        ds = next(s for s in result if s.name == "unused_function")
        assert ds.kind == "function"

    def test_dead_import_flagged(self):
        result = self.dcd.scan_file(DEAD_IMPORT)
        names = {s.name for s in result}
        assert "os" in names

    def test_used_import_not_flagged(self):
        result = self.dcd.scan_file(DEAD_IMPORT)
        names = {s.name for s in result}
        assert "sys" not in names

    def test_dead_class_flagged(self):
        result = self.dcd.scan_file(DEAD_CLASS)
        names = {s.name for s in result}
        assert "Unused" in names

    def test_private_names_skipped(self):
        src = """\
def _private():
    pass

_x = 1
"""
        result = self.dcd.scan_file(src)
        names = {s.name for s in result}
        assert "_private" not in names
        assert "_x" not in names

    def test_all_caps_constants_skipped(self):
        src = "MAX_RETRIES = 3\n"
        result = self.dcd.scan_file(src)
        names = {s.name for s in result}
        assert "MAX_RETRIES" not in names

    def test_file_path_recorded(self):
        result = self.dcd.scan_file(DEAD_FN, file_path="mymodule.py")
        assert all(s.file == "mymodule.py" for s in result)

    def test_line_number_recorded(self):
        result = self.dcd.scan_file(DEAD_FN)
        ds = next(s for s in result if s.name == "unused_function")
        assert ds.line == 1
