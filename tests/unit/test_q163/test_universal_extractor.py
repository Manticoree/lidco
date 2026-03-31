"""Tests for UniversalExtractor — Task 928."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from lidco.ast.treesitter_parser import TreeSitterParser
from lidco.ast.universal_extractor import UniversalExtractor, ExtractedSymbol


class TestExtractedSymbol(unittest.TestCase):
    def test_dataclass_fields(self):
        s = ExtractedSymbol(name="foo", kind="function", language="python", line=1)
        self.assertEqual(s.name, "foo")
        self.assertEqual(s.kind, "function")
        self.assertEqual(s.language, "python")
        self.assertEqual(s.line, 1)
        self.assertIsNone(s.end_line)
        self.assertEqual(s.signature, "")

    def test_with_all_fields(self):
        s = ExtractedSymbol(
            name="Bar", kind="class", language="java", line=5,
            end_line=20, signature="class Bar extends Foo",
        )
        self.assertEqual(s.end_line, 20)
        self.assertIn("Bar", s.signature)


class TestPythonExtraction(unittest.TestCase):
    def setUp(self):
        self.parser = TreeSitterParser()
        self.extractor = UniversalExtractor(self.parser)

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_extract_function(self):
        source = "def hello():\n    pass\n"
        syms = self.extractor.extract(source, "python")
        funcs = [s for s in syms if s.kind == "function"]
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "hello")
        self.assertEqual(funcs[0].line, 1)

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_extract_class(self):
        source = "class MyClass:\n    pass\n"
        syms = self.extractor.extract(source, "python")
        classes = [s for s in syms if s.kind == "class"]
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0].name, "MyClass")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_extract_method(self):
        source = "class Foo:\n    def bar(self):\n        pass\n"
        syms = self.extractor.extract(source, "python")
        methods = [s for s in syms if s.kind == "method"]
        self.assertEqual(len(methods), 1)
        self.assertEqual(methods[0].name, "bar")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_extract_import(self):
        source = "import os\nfrom sys import argv\n"
        syms = self.extractor.extract(source, "python")
        imports = [s for s in syms if s.kind == "import"]
        self.assertEqual(len(imports), 2)

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_extract_async_def(self):
        source = "async def fetch():\n    pass\n"
        syms = self.extractor.extract(source, "python")
        funcs = [s for s in syms if s.kind == "function"]
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "fetch")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_extract_mixed(self):
        source = (
            "import json\n"
            "class Foo:\n"
            "    def bar(self):\n"
            "        pass\n"
            "def baz():\n"
            "    pass\n"
        )
        syms = self.extractor.extract(source, "python")
        kinds = {s.kind for s in syms}
        self.assertIn("import", kinds)
        self.assertIn("class", kinds)
        self.assertIn("method", kinds)
        self.assertIn("function", kinds)


class TestJavaScriptExtraction(unittest.TestCase):
    def setUp(self):
        self.parser = TreeSitterParser()
        self.extractor = UniversalExtractor(self.parser)

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_extract_function(self):
        source = "function greet(name) {\n  return name;\n}\n"
        syms = self.extractor.extract(source, "javascript")
        funcs = [s for s in syms if s.kind == "function"]
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "greet")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_extract_class(self):
        source = "class Widget {\n  render() {}\n}\n"
        syms = self.extractor.extract(source, "javascript")
        classes = [s for s in syms if s.kind == "class"]
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0].name, "Widget")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_extract_const(self):
        source = "const MAX = 100;\n"
        syms = self.extractor.extract(source, "javascript")
        vars_ = [s for s in syms if s.kind == "variable"]
        self.assertEqual(len(vars_), 1)
        self.assertEqual(vars_[0].name, "MAX")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_extract_import(self):
        source = "import React from 'react';\n"
        syms = self.extractor.extract(source, "javascript")
        imports = [s for s in syms if s.kind == "import"]
        self.assertEqual(len(imports), 1)

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_extract_export_function(self):
        source = "export function doStuff() {}\n"
        syms = self.extractor.extract(source, "javascript")
        funcs = [s for s in syms if s.kind == "function"]
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "doStuff")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_typescript_uses_js_extractor(self):
        source = "export class Service {}\n"
        syms = self.extractor.extract(source, "typescript")
        classes = [s for s in syms if s.kind == "class"]
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0].language, "typescript")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_extract_method(self):
        source = "class X {\n  render() {\n  }\n}\n"
        syms = self.extractor.extract(source, "javascript")
        methods = [s for s in syms if s.kind == "method"]
        self.assertEqual(len(methods), 1)
        self.assertEqual(methods[0].name, "render")


class TestGenericExtraction(unittest.TestCase):
    def setUp(self):
        self.parser = TreeSitterParser()
        self.extractor = UniversalExtractor(self.parser)

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_generic_function(self):
        source = "func main() {\n}\n"
        syms = self.extractor.extract(source, "go")
        funcs = [s for s in syms if s.kind == "function"]
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "main")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_generic_struct(self):
        source = "struct Point {\n  x: f64,\n  y: f64,\n}\n"
        syms = self.extractor.extract(source, "rust")
        classes = [s for s in syms if s.kind == "class"]
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0].name, "Point")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_generic_fn(self):
        source = "fn compute(x: i32) -> i32 {\n  x * 2\n}\n"
        syms = self.extractor.extract(source, "rust")
        funcs = [s for s in syms if s.kind == "function"]
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "compute")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_empty_source(self):
        syms = self.extractor.extract("", "go")
        self.assertEqual(syms, [])


if __name__ == "__main__":
    unittest.main()
