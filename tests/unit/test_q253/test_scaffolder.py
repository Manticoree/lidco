"""Tests for TestScaffolder (Q253)."""
from __future__ import annotations

import unittest

from lidco.testgen.scaffolder import ScaffoldResult, TestScaffolder


class TestScaffoldResult(unittest.TestCase):
    def test_frozen(self):
        r = ScaffoldResult(test_file="x", test_classes=["A"], test_methods=["m"])
        with self.assertRaises(AttributeError):
            r.test_file = "y"  # type: ignore[misc]

    def test_defaults(self):
        r = ScaffoldResult(test_file="x")
        self.assertEqual(r.test_classes, [])
        self.assertEqual(r.test_methods, [])


class TestExtractFunctions(unittest.TestCase):
    def setUp(self):
        self.scaffolder = TestScaffolder()

    def test_basic(self):
        source = "def foo():\n    pass\ndef bar():\n    pass\n"
        self.assertEqual(self.scaffolder.extract_functions(source), ["foo", "bar"])

    def test_skips_private(self):
        source = "def _private():\n    pass\ndef public():\n    pass\n"
        self.assertEqual(self.scaffolder.extract_functions(source), ["public"])

    def test_async_function(self):
        source = "async def fetch():\n    pass\n"
        self.assertEqual(self.scaffolder.extract_functions(source), ["fetch"])

    def test_bad_syntax(self):
        self.assertEqual(self.scaffolder.extract_functions("def (broken"), [])

    def test_empty_source(self):
        self.assertEqual(self.scaffolder.extract_functions(""), [])

    def test_nested_functions_ignored(self):
        source = "def outer():\n    def inner():\n        pass\n"
        self.assertEqual(self.scaffolder.extract_functions(source), ["outer"])


class TestExtractClasses(unittest.TestCase):
    def setUp(self):
        self.scaffolder = TestScaffolder()

    def test_basic(self):
        source = "class Foo:\n    def bar(self):\n        pass\n"
        result = self.scaffolder.extract_classes(source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Foo")
        self.assertEqual(result[0]["methods"], ["bar"])

    def test_skips_private_methods(self):
        source = "class Foo:\n    def _priv(self):\n        pass\n    def pub(self):\n        pass\n"
        result = self.scaffolder.extract_classes(source)
        self.assertEqual(result[0]["methods"], ["pub"])

    def test_multiple_classes(self):
        source = "class A:\n    pass\nclass B:\n    def run(self):\n        pass\n"
        result = self.scaffolder.extract_classes(source)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "A")
        self.assertEqual(result[1]["name"], "B")

    def test_bad_syntax(self):
        self.assertEqual(self.scaffolder.extract_classes("class (broken"), [])

    def test_empty_source(self):
        self.assertEqual(self.scaffolder.extract_classes(""), [])

    def test_async_methods_included(self):
        source = "class S:\n    async def fetch(self):\n        pass\n"
        result = self.scaffolder.extract_classes(source)
        self.assertEqual(result[0]["methods"], ["fetch"])


class TestScaffold(unittest.TestCase):
    def setUp(self):
        self.scaffolder = TestScaffolder()

    def test_scaffold_class(self):
        source = "class Calc:\n    def add(self):\n        pass\n    def sub(self):\n        pass\n"
        result = self.scaffolder.scaffold(source)
        self.assertIn("TestCalc", result.test_classes)
        self.assertIn("test_add", result.test_methods)
        self.assertIn("test_sub", result.test_methods)
        self.assertIn("class TestCalc", result.test_file)

    def test_scaffold_functions_only(self):
        source = "def hello():\n    pass\n"
        result = self.scaffolder.scaffold(source)
        self.assertIn("TestFunctions", result.test_classes)
        self.assertIn("test_hello", result.test_methods)

    def test_scaffold_filter_class(self):
        source = "class A:\n    def m1(self):\n        pass\nclass B:\n    def m2(self):\n        pass\n"
        result = self.scaffolder.scaffold(source, class_name="B")
        self.assertIn("TestB", result.test_classes)
        self.assertNotIn("TestA", result.test_classes)

    def test_scaffold_empty(self):
        result = self.scaffolder.scaffold("")
        self.assertIn("No classes or functions found", result.test_file)
        self.assertEqual(result.test_classes, [])

    def test_scaffold_has_imports(self):
        source = "class X:\n    def go(self):\n        pass\n"
        result = self.scaffolder.scaffold(source)
        self.assertIn("import unittest", result.test_file)

    def test_scaffold_todo_in_methods(self):
        source = "class X:\n    def go(self):\n        pass\n"
        result = self.scaffolder.scaffold(source)
        self.assertIn("self.fail", result.test_file)


class TestScaffoldForFile(unittest.TestCase):
    def setUp(self):
        self.scaffolder = TestScaffolder()

    def test_includes_filename(self):
        source = "class Foo:\n    def bar(self):\n        pass\n"
        output = self.scaffolder.scaffold_for_file("my_module.py", source)
        self.assertIn("my_module.py", output)
        self.assertIn("import", output)

    def test_generates_test_class(self):
        source = "def greet():\n    pass\n"
        output = self.scaffolder.scaffold_for_file("greet.py", source)
        self.assertIn("TestFunctions", output)

    def test_empty_source(self):
        output = self.scaffolder.scaffold_for_file("empty.py", "")
        self.assertIn("empty.py", output)


if __name__ == "__main__":
    unittest.main()
