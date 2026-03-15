"""Tests for SymbolIndex and SymbolIndexBuilder — Task 344."""

from __future__ import annotations

import pytest

from lidco.analysis.symbol_index import SymbolDef, SymbolIndex, SymbolIndexBuilder


SRC_A = """\
import os
from sys import path

MY_CONST = 42

def standalone_func():
    pass

class MyClass:
    def method_one(self):
        pass

    def method_two(self):
        pass
"""

SRC_B = """\
def another_func():
    return 1

class AnotherClass:
    pass
"""


class TestSymbolDef:
    def test_frozen(self):
        s = SymbolDef(name="f", kind="function", file="x.py", line=1, qualified="f")
        with pytest.raises((AttributeError, TypeError)):
            s.name = "g"  # type: ignore[misc]


class TestSymbolIndex:
    def test_find_by_name(self):
        idx = SymbolIndex()
        s = SymbolDef(name="foo", kind="function", file="x.py", line=1, qualified="foo")
        idx.add(s)
        result = idx.find("foo")
        assert len(result) == 1
        assert result[0].name == "foo"

    def test_find_by_qualified(self):
        idx = SymbolIndex()
        s = SymbolDef(name="method", kind="method", file="x.py", line=5,
                      qualified="MyClass.method")
        idx.add(s)
        result = idx.find("MyClass.method")
        assert len(result) == 1

    def test_find_missing(self):
        idx = SymbolIndex()
        assert idx.find("nonexistent") == []

    def test_find_by_kind(self):
        idx = SymbolIndex()
        idx.add(SymbolDef("f", "function", "x.py", 1, "f"))
        idx.add(SymbolDef("C", "class", "x.py", 5, "C"))
        fns = idx.find_by_kind("function")
        assert len(fns) == 1
        assert fns[0].name == "f"

    def test_find_in_file(self):
        idx = SymbolIndex()
        idx.add(SymbolDef("f", "function", "a.py", 1, "f"))
        idx.add(SymbolDef("g", "function", "b.py", 1, "g"))
        result = idx.find_in_file("a.py")
        assert len(result) == 1

    def test_all_names(self):
        idx = SymbolIndex()
        idx.add(SymbolDef("f", "function", "x.py", 1, "f"))
        idx.add(SymbolDef("C", "class", "x.py", 5, "C"))
        assert idx.all_names() == {"f", "C"}

    def test_len(self):
        idx = SymbolIndex()
        assert len(idx) == 0
        idx.add(SymbolDef("f", "function", "x.py", 1, "f"))
        assert len(idx) == 1


class TestSymbolIndexBuilder:
    def setup_method(self):
        self.builder = SymbolIndexBuilder()

    def test_build_empty(self):
        idx = self.builder.build({})
        assert len(idx) == 0

    def test_finds_function(self):
        idx = self.builder.build({"a.py": SRC_A})
        names = idx.all_names()
        assert "standalone_func" in names

    def test_finds_class(self):
        idx = self.builder.build({"a.py": SRC_A})
        classes = idx.find_by_kind("class")
        assert any(c.name == "MyClass" for c in classes)

    def test_finds_methods(self):
        idx = self.builder.build({"a.py": SRC_A})
        methods = idx.find_by_kind("method")
        names = {m.name for m in methods}
        assert "method_one" in names
        assert "method_two" in names

    def test_method_qualified_name(self):
        idx = self.builder.build({"a.py": SRC_A})
        result = idx.find("MyClass.method_one")
        assert len(result) == 1

    def test_finds_imports(self):
        idx = self.builder.build({"a.py": SRC_A})
        imports = idx.find_by_kind("import")
        names = {i.name for i in imports}
        assert "os" in names

    def test_syntax_error_skipped(self):
        idx = self.builder.build({"bad.py": "def broken(:"})
        assert len(idx) == 0

    def test_multiple_files(self):
        idx = self.builder.build({"a.py": SRC_A, "b.py": SRC_B})
        files = {s.file for s in idx._defs}
        assert "a.py" in files
        assert "b.py" in files

    def test_file_path_recorded(self):
        idx = self.builder.build({"myfile.py": SRC_A})
        fns = idx.find_by_kind("function")
        assert all(s.file == "myfile.py" for s in fns)
