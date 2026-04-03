"""Tests for lidco.types.annotator_v2 — TypeAnnotatorV2."""
from __future__ import annotations

import unittest

from lidco.types.annotator_v2 import Annotation, TypeAnnotatorV2
from lidco.types.inferrer import InferredType


class TestAnnotation(unittest.TestCase):
    def test_frozen(self):
        a = Annotation(line=1, original="x = 5", annotated="x: int = 5")
        with self.assertRaises(AttributeError):
            a.line = 2  # type: ignore[misc]


class TestAnnotateFunction(unittest.TestCase):
    def setUp(self):
        self.ann = TypeAnnotatorV2()

    def test_add_param_types(self):
        src = "def foo(x, y):\n    return x + y\n"
        result = self.ann.annotate_function(src, "foo", {"x": "int", "y": "int"})
        self.assertIn("x: int", result)
        self.assertIn("y: int", result)

    def test_add_return_type(self):
        src = "def foo(x):\n    return x\n"
        result = self.ann.annotate_function(src, "foo", {}, return_type="int")
        self.assertIn("-> int", result)

    def test_both_param_and_return(self):
        src = "def add(a, b):\n    return a + b\n"
        result = self.ann.annotate_function(src, "add", {"a": "int", "b": "int"}, "int")
        self.assertIn("a: int", result)
        self.assertIn("b: int", result)
        self.assertIn("-> int", result)

    def test_no_change_for_wrong_name(self):
        src = "def foo(x):\n    pass\n"
        result = self.ann.annotate_function(src, "bar", {"x": "int"})
        self.assertEqual(result, src)

    def test_syntax_error_returns_source(self):
        src = "def broken(:"
        result = self.ann.annotate_function(src, "broken", {"x": "int"})
        self.assertEqual(result, src)

    def test_does_not_duplicate_return_type(self):
        src = "def foo(x) -> str:\n    return x\n"
        result = self.ann.annotate_function(src, "foo", {}, return_type="str")
        # Should not add a second ->.
        self.assertEqual(result.count("->"), 1)


class TestAnnotateAll(unittest.TestCase):
    def setUp(self):
        self.ann = TypeAnnotatorV2()

    def test_annotate_from_inferred(self):
        src = "x = 5\n"
        inferred = [InferredType(name="x", type="int", confidence=0.95, source="assignment")]
        result = self.ann.annotate_all(src, inferred)
        self.assertIn("x: int", result)

    def test_annotate_return_type(self):
        src = "def greet():\n    return 'hi'\n"
        inferred = [InferredType(name="greet", type="str", confidence=0.9, source="return")]
        result = self.ann.annotate_all(src, inferred)
        self.assertIn("-> str", result)

    def test_no_change_when_empty(self):
        src = "pass\n"
        result = self.ann.annotate_all(src, [])
        self.assertEqual(result, src)


class TestGenerateStub(unittest.TestCase):
    def setUp(self):
        self.ann = TypeAnnotatorV2()

    def test_function_stub(self):
        src = "def foo(x: int, y: str) -> bool:\n    return len(y) > x\n"
        stub = self.ann.generate_stub(src)
        self.assertIn("def foo(x: int, y: str) -> bool: ...", stub)

    def test_class_stub(self):
        src = "class Foo:\n    def bar(self) -> int:\n        return 1\n"
        stub = self.ann.generate_stub(src)
        self.assertIn("class Foo:", stub)
        self.assertIn("def bar(self) -> int: ...", stub)

    def test_module_level_constant(self):
        src = "VERSION = 1\n"
        stub = self.ann.generate_stub(src)
        self.assertIn("VERSION: int", stub)

    def test_import_preserved(self):
        src = "import os\n\ndef foo() -> None:\n    pass\n"
        stub = self.ann.generate_stub(src)
        self.assertIn("import os", stub)

    def test_empty_source(self):
        stub = self.ann.generate_stub("")
        self.assertEqual(stub, "")

    def test_syntax_error(self):
        stub = self.ann.generate_stub("def broken(:")
        self.assertEqual(stub, "")

    def test_async_function_stub(self):
        src = "async def fetch(url: str) -> str:\n    return ''\n"
        stub = self.ann.generate_stub(src)
        self.assertIn("async def fetch(url: str) -> str: ...", stub)


class TestDiff(unittest.TestCase):
    def setUp(self):
        self.ann = TypeAnnotatorV2()

    def test_diff_shows_changes(self):
        original = "x = 5\n"
        annotated = "x: int = 5\n"
        diff = self.ann.diff(original, annotated)
        self.assertTrue(len(diff) > 0)
        # Unified diff contains +/- lines.
        joined = "".join(diff)
        self.assertIn("-x = 5", joined)
        self.assertIn("+x: int = 5", joined)

    def test_diff_empty_when_identical(self):
        src = "x = 5\n"
        diff = self.ann.diff(src, src)
        self.assertEqual(diff, [])


if __name__ == "__main__":
    unittest.main()
