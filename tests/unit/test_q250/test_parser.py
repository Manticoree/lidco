"""Tests for UniversalParser (Q250)."""
from __future__ import annotations

import unittest

from lidco.polyglot.parser import Symbol, UniversalParser


class TestSymbol(unittest.TestCase):
    def test_frozen(self):
        s = Symbol(name="foo", kind="function", language="python")
        with self.assertRaises(AttributeError):
            s.name = "bar"  # type: ignore[misc]

    def test_defaults(self):
        s = Symbol(name="x", kind="class", language="go")
        self.assertEqual(s.file, "")
        self.assertEqual(s.line, 0)

    def test_fields(self):
        s = Symbol(name="main", kind="function", language="rust", file="lib.rs", line=10)
        self.assertEqual(s.name, "main")
        self.assertEqual(s.kind, "function")
        self.assertEqual(s.language, "rust")
        self.assertEqual(s.file, "lib.rs")
        self.assertEqual(s.line, 10)


class TestParsePython(unittest.TestCase):
    def setUp(self):
        self.parser = UniversalParser()

    def test_functions(self):
        code = "def foo():\n    pass\ndef bar():\n    pass"
        syms = self.parser.parse_python(code)
        names = [s.name for s in syms]
        self.assertIn("foo", names)
        self.assertIn("bar", names)

    def test_classes(self):
        code = "class MyClass:\n    pass"
        syms = self.parser.parse_python(code)
        self.assertEqual(len(syms), 1)
        self.assertEqual(syms[0].name, "MyClass")
        self.assertEqual(syms[0].kind, "class")

    def test_async_def(self):
        code = "async def handler():\n    pass"
        syms = self.parser.parse_python(code)
        names = [s.name for s in syms]
        self.assertIn("handler", names)

    def test_language_is_python(self):
        code = "def x(): pass"
        syms = self.parser.parse_python(code)
        self.assertTrue(all(s.language == "python" for s in syms))

    def test_line_numbers(self):
        code = "# comment\ndef second():\n    pass"
        syms = self.parser.parse_python(code)
        self.assertEqual(syms[0].line, 2)

    def test_empty(self):
        self.assertEqual(self.parser.parse_python(""), [])

    def test_no_duplicates(self):
        code = "def dup():\n    pass\ndef dup():\n    pass"
        syms = self.parser.parse_python(code)
        names = [s.name for s in syms if s.name == "dup"]
        self.assertEqual(len(names), 1)


class TestParseJavaScript(unittest.TestCase):
    def setUp(self):
        self.parser = UniversalParser()

    def test_function_declaration(self):
        code = "function greet() {}"
        syms = self.parser.parse_javascript(code)
        self.assertEqual(len(syms), 1)
        self.assertEqual(syms[0].name, "greet")
        self.assertEqual(syms[0].kind, "function")

    def test_class(self):
        code = "class App {}"
        syms = self.parser.parse_javascript(code)
        self.assertEqual(syms[0].name, "App")
        self.assertEqual(syms[0].kind, "class")

    def test_const_function(self):
        code = "const handler = function() {}"
        syms = self.parser.parse_javascript(code)
        names = [s.name for s in syms]
        self.assertIn("handler", names)

    def test_const_variable(self):
        code = "const PORT = 3000"
        syms = self.parser.parse_javascript(code)
        self.assertTrue(any(s.name == "PORT" for s in syms))

    def test_language_is_javascript(self):
        code = "function x() {}"
        syms = self.parser.parse_javascript(code)
        self.assertTrue(all(s.language == "javascript" for s in syms))

    def test_empty(self):
        self.assertEqual(self.parser.parse_javascript(""), [])


class TestParseGeneric(unittest.TestCase):
    def setUp(self):
        self.parser = UniversalParser()

    def test_go(self):
        code = "func main() {\n}\ntype Server struct {\n}"
        syms = self.parser.parse(code, "go")
        names = [s.name for s in syms]
        self.assertIn("main", names)
        self.assertIn("Server", names)

    def test_rust(self):
        code = "fn process() {}\npub struct Config {}\nenum Status {}"
        syms = self.parser.parse(code, "rust")
        names = [s.name for s in syms]
        self.assertIn("process", names)
        self.assertIn("Config", names)
        self.assertIn("Status", names)

    def test_java(self):
        code = "public class App {\n    public void run() {}\n}"
        syms = self.parser.parse(code, "java")
        names = [s.name for s in syms]
        self.assertIn("App", names)

    def test_c(self):
        code = '#include <stdio.h>\nint main(int argc) {\n}\n#define MAX 100'
        syms = self.parser.parse(code, "c")
        names = [s.name for s in syms]
        self.assertIn("main", names)
        self.assertIn("MAX", names)

    def test_python_delegates(self):
        code = "def foo(): pass"
        syms = self.parser.parse(code, "python")
        self.assertEqual(syms[0].name, "foo")

    def test_javascript_delegates(self):
        code = "function bar() {}"
        syms = self.parser.parse(code, "javascript")
        self.assertEqual(syms[0].name, "bar")

    def test_typescript_delegates(self):
        code = "function baz() {}"
        syms = self.parser.parse(code, "typescript")
        self.assertEqual(syms[0].name, "baz")

    def test_unknown_language(self):
        syms = self.parser.parse("stuff", "brainfuck")
        self.assertEqual(syms, [])


class TestExtractImports(unittest.TestCase):
    def setUp(self):
        self.parser = UniversalParser()

    def test_python_import(self):
        code = "import os\nfrom pathlib import Path"
        imports = self.parser.extract_imports(code, "python")
        self.assertIn("os", imports)
        self.assertIn("pathlib", imports)

    def test_javascript_require(self):
        code = "const fs = require('fs')\nconst path = require('path')"
        imports = self.parser.extract_imports(code, "javascript")
        self.assertIn("fs", imports)
        self.assertIn("path", imports)

    def test_javascript_import(self):
        code = "import React from 'react'"
        imports = self.parser.extract_imports(code, "javascript")
        self.assertIn("react", imports)

    def test_rust_use(self):
        code = "use std::io"
        imports = self.parser.extract_imports(code, "rust")
        self.assertIn("std::io", imports)

    def test_c_include(self):
        code = '#include <stdio.h>\n#include "mylib.h"'
        imports = self.parser.extract_imports(code, "c")
        self.assertIn("stdio.h", imports)
        self.assertIn("mylib.h", imports)

    def test_no_duplicates(self):
        code = "import os\nimport os"
        imports = self.parser.extract_imports(code, "python")
        self.assertEqual(imports.count("os"), 1)

    def test_unknown_lang(self):
        self.assertEqual(self.parser.extract_imports("x", "unknown"), [])

    def test_empty(self):
        self.assertEqual(self.parser.extract_imports("", "python"), [])


if __name__ == "__main__":
    unittest.main()
