"""Tests for python_extractor — Q125."""
from __future__ import annotations
import unittest
from lidco.analysis.python_extractor import PythonExtractor, ExtractionResult


class TestExtractionResult(unittest.TestCase):
    def test_creation(self):
        r = ExtractionResult(module="mymod")
        self.assertEqual(r.module, "mymod")
        self.assertEqual(r.definitions, [])
        self.assertEqual(r.imports, [])
        self.assertEqual(r.errors, [])


class TestPythonExtractor(unittest.TestCase):
    def setUp(self):
        self.ex = PythonExtractor()

    def test_extract_function(self):
        src = "def foo(): pass"
        result = self.ex.extract(src, "mod")
        names = [d.name for d in result.definitions]
        self.assertIn("foo", names)

    def test_extract_class(self):
        src = "class Bar: pass"
        result = self.ex.extract(src, "mod")
        names = [d.name for d in result.definitions]
        self.assertIn("Bar", names)

    def test_extract_variable(self):
        src = "x = 42"
        result = self.ex.extract(src, "mod")
        names = [d.name for d in result.definitions]
        self.assertIn("x", names)

    def test_extract_import(self):
        src = "import os"
        result = self.ex.extract(src, "mod")
        self.assertIn("os", result.imports)

    def test_extract_from_import(self):
        src = "from pathlib import Path"
        result = self.ex.extract(src, "mod")
        self.assertIn("Path", result.imports)

    def test_extract_async_function(self):
        src = "async def afoo(): pass"
        result = self.ex.extract(src, "mod")
        names = [d.name for d in result.definitions]
        self.assertIn("afoo", names)

    def test_extract_docstring(self):
        src = 'def foo():\n    """My doc."""\n    pass'
        result = self.ex.extract(src, "mod")
        fn = next(d for d in result.definitions if d.name == "foo")
        self.assertEqual(fn.docstring, "My doc.")

    def test_extract_class_docstring(self):
        src = 'class Bar:\n    """Bar doc."""\n    pass'
        result = self.ex.extract(src, "mod")
        cls = next(d for d in result.definitions if d.name == "Bar")
        self.assertEqual(cls.docstring, "Bar doc.")

    def test_syntax_error_adds_to_errors(self):
        src = "def foo("
        result = self.ex.extract(src, "mod")
        self.assertTrue(len(result.errors) > 0)
        self.assertEqual(result.definitions, [])

    def test_module_name_stored(self):
        src = "x = 1"
        result = self.ex.extract(src, "mypackage.module")
        self.assertEqual(result.module, "mypackage.module")

    def test_kind_function(self):
        src = "def foo(): pass"
        result = self.ex.extract(src, "m")
        fn = next(d for d in result.definitions if d.name == "foo")
        self.assertEqual(fn.kind, "function")

    def test_kind_class(self):
        src = "class Foo: pass"
        result = self.ex.extract(src, "m")
        cls = next(d for d in result.definitions if d.name == "Foo")
        self.assertEqual(cls.kind, "class")

    def test_kind_variable(self):
        src = "x = 1"
        result = self.ex.extract(src, "m")
        var = next(d for d in result.definitions if d.name == "x")
        self.assertEqual(var.kind, "variable")

    def test_kind_import(self):
        src = "import sys"
        result = self.ex.extract(src, "m")
        imp = next(d for d in result.definitions if d.name == "sys")
        self.assertEqual(imp.kind, "import")

    def test_extract_file_with_read_fn(self):
        def read_fn(path):
            return "def bar(): pass"
        result = self.ex.extract_file("dummy.py", read_fn=read_fn)
        names = [d.name for d in result.definitions]
        self.assertIn("bar", names)

    def test_extract_file_read_error(self):
        def read_fn(path):
            raise OSError("not found")
        result = self.ex.extract_file("missing.py", read_fn=read_fn)
        self.assertTrue(len(result.errors) > 0)

    def test_empty_source(self):
        result = self.ex.extract("", "m")
        self.assertEqual(result.definitions, [])
        self.assertEqual(result.errors, [])

    def test_multiple_definitions(self):
        src = "def a(): pass\ndef b(): pass\nclass C: pass"
        result = self.ex.extract(src, "m")
        names = [d.name for d in result.definitions]
        self.assertIn("a", names)
        self.assertIn("b", names)
        self.assertIn("C", names)

    def test_import_alias(self):
        src = "import numpy as np"
        result = self.ex.extract(src, "m")
        self.assertIn("np", result.imports)

    def test_from_import_alias(self):
        src = "from os.path import join as j"
        result = self.ex.extract(src, "m")
        self.assertIn("j", result.imports)

    def test_line_numbers(self):
        src = "x = 1\ndef foo(): pass"
        result = self.ex.extract(src, "m")
        var = next(d for d in result.definitions if d.name == "x")
        self.assertEqual(var.line, 1)
        fn = next(d for d in result.definitions if d.name == "foo")
        self.assertEqual(fn.line, 2)


if __name__ == "__main__":
    unittest.main()
