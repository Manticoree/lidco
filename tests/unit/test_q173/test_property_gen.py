"""Tests for lidco.testing.property_gen — Task 978."""

import unittest

from lidco.testing.property_gen import (
    FunctionSignature,
    PropertyTest,
    PropertyTestGenerator,
)


class TestPropertyTestGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = PropertyTestGenerator()

    def test_extract_signatures_basic(self):
        source = "def add(a, b):\n    return a + b"
        sigs = self.gen.extract_signatures(source)
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].name, "add")
        self.assertEqual(len(sigs[0].params), 2)

    def test_extract_signatures_with_annotations(self):
        source = "def add(a: int, b: int) -> int:\n    return a + b"
        sigs = self.gen.extract_signatures(source)
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].params[0]["annotation"], "int")
        self.assertEqual(sigs[0].return_annotation, "int")

    def test_extract_signatures_async(self):
        source = "async def fetch(url: str) -> str:\n    return url"
        sigs = self.gen.extract_signatures(source)
        self.assertEqual(len(sigs), 1)
        self.assertTrue(sigs[0].is_async)

    def test_extract_signatures_skips_private(self):
        source = "def _private():\n    pass\ndef public():\n    pass"
        sigs = self.gen.extract_signatures(source)
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].name, "public")

    def test_extract_signatures_with_docstring(self):
        source = 'def greet(name: str):\n    """Say hello."""\n    return f"hi {name}"'
        sigs = self.gen.extract_signatures(source)
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].docstring, "Say hello.")

    def test_extract_signatures_syntax_error(self):
        source = "def broken(:\n    pass"
        sigs = self.gen.extract_signatures(source)
        self.assertEqual(len(sigs), 0)

    def test_generate_tests_smoke(self):
        source = "def add(a: int, b: int) -> int:\n    return a + b"
        tests = self.gen.generate_tests(source)
        smoke_tests = [t for t in tests if t.pattern == "smoke"]
        self.assertTrue(len(smoke_tests) > 0)
        self.assertIn("smoke", smoke_tests[0].test_name)

    def test_generate_tests_roundtrip(self):
        source = "def identity(x: int) -> int:\n    return x"
        tests = self.gen.generate_tests(source)
        rt = [t for t in tests if t.pattern == "roundtrip"]
        self.assertTrue(len(rt) > 0)

    def test_generate_tests_invariant(self):
        source = "def check(x: int) -> bool:\n    return x > 0"
        tests = self.gen.generate_tests(source)
        inv = [t for t in tests if t.pattern == "invariant"]
        self.assertTrue(len(inv) > 0)

    def test_type_strategies_defaults(self):
        strats = self.gen.type_strategies
        self.assertIn("int", strats)
        self.assertIn("float", strats)
        self.assertIn("str", strats)
        self.assertIn("bool", strats)
        self.assertIn("list", strats)
        self.assertIn("dict", strats)

    def test_generate_args_typed(self):
        sig = FunctionSignature(
            name="f", params=[{"name": "x", "annotation": "int"}],
            return_annotation=None, docstring=None,
        )
        args = self.gen._generate_args(sig)
        self.assertIn("random.randint", args)

    def test_generate_args_untyped(self):
        sig = FunctionSignature(
            name="f", params=[{"name": "x", "annotation": None}],
            return_annotation=None, docstring=None,
        )
        args = self.gen._generate_args(sig)
        self.assertEqual(args, "None")

    def test_generate_args_empty(self):
        sig = FunctionSignature(
            name="f", params=[], return_annotation=None, docstring=None,
        )
        args = self.gen._generate_args(sig)
        self.assertEqual(args, "")

    def test_format_test_file(self):
        source = "def add(a: int, b: int) -> int:\n    return a + b"
        tests = self.gen.generate_tests(source)
        output = self.gen.format_test_file(tests)
        self.assertIn("import random", output)
        self.assertIn("class TestProperties", output)

    def test_format_test_file_empty(self):
        output = self.gen.format_test_file([])
        self.assertIn("No property tests generated", output)

    def test_generate_tests_no_functions(self):
        source = "x = 42\ny = 'hello'"
        tests = self.gen.generate_tests(source)
        self.assertEqual(len(tests), 0)

    def test_extract_skips_self_param(self):
        source = "class Foo:\n    def method(self, x: int):\n        pass"
        sigs = self.gen.extract_signatures(source)
        self.assertEqual(len(sigs), 1)
        param_names = [p["name"] for p in sigs[0].params]
        self.assertNotIn("self", param_names)

    def test_property_test_dataclass(self):
        pt = PropertyTest(
            function_name="foo", module_path="mod",
            test_name="test_foo_smoke", test_code="pass",
            pattern="smoke", description="desc",
        )
        self.assertEqual(pt.function_name, "foo")
        self.assertEqual(pt.pattern, "smoke")

    def test_no_roundtrip_when_types_differ(self):
        source = "def convert(x: int) -> str:\n    return str(x)"
        tests = self.gen.generate_tests(source)
        rt = [t for t in tests if t.pattern == "roundtrip"]
        self.assertEqual(len(rt), 0)

    def test_no_invariant_when_not_bool(self):
        source = "def add(a: int, b: int) -> int:\n    return a + b"
        tests = self.gen.generate_tests(source)
        inv = [t for t in tests if t.pattern == "invariant"]
        self.assertEqual(len(inv), 0)


if __name__ == "__main__":
    unittest.main()
