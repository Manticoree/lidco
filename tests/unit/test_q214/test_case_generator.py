"""Tests for test_intel.case_generator — TestCase, TestCaseGenerator."""
from __future__ import annotations

import unittest

from lidco.test_intel.case_generator import TestCase, TestCaseGenerator


class TestTestCase(unittest.TestCase):
    def test_frozen(self):
        tc = TestCase(name="t", function_name="f")
        with self.assertRaises(AttributeError):
            tc.name = "x"  # type: ignore[misc]

    def test_defaults(self):
        tc = TestCase(name="t", function_name="f")
        self.assertEqual(tc.inputs, {})
        self.assertIsNone(tc.expected)
        self.assertEqual(tc.assertion, "assertEqual")
        self.assertEqual(tc.description, "")

    def test_fields(self):
        tc = TestCase(
            name="test_add",
            function_name="add",
            inputs={"a": 1, "b": 2},
            expected=3,
            assertion="assertEqual",
            description="basic add",
        )
        self.assertEqual(tc.name, "test_add")
        self.assertEqual(tc.function_name, "add")
        self.assertEqual(tc.inputs, {"a": 1, "b": 2})
        self.assertEqual(tc.expected, 3)
        self.assertEqual(tc.description, "basic add")

    def test_equality(self):
        a = TestCase(name="t", function_name="f", inputs={"x": 1})
        b = TestCase(name="t", function_name="f", inputs={"x": 1})
        self.assertEqual(a, b)


class TestTestCaseGenerator(unittest.TestCase):
    def test_generate_simple_function(self):
        src = "def add(a: int, b: int) -> int:\n    return a + b\n"
        gen = TestCaseGenerator()
        cases = gen.generate(src, "add")
        self.assertGreater(len(cases), 0)
        self.assertTrue(all(c.function_name == "add" for c in cases))

    def test_generate_all_functions(self):
        src = "def foo(x: str): pass\ndef bar(y: int): pass\n"
        gen = TestCaseGenerator()
        cases = gen.generate(src)
        names = {c.function_name for c in cases}
        self.assertIn("foo", names)
        self.assertIn("bar", names)

    def test_generate_no_params(self):
        src = "def noop(): pass\n"
        gen = TestCaseGenerator()
        cases = gen.generate(src, "noop")
        self.assertGreater(len(cases), 0)
        self.assertEqual(cases[0].inputs, {})

    def test_generate_invalid_source(self):
        gen = TestCaseGenerator()
        cases = gen.generate("not valid python !!!", "f")
        self.assertEqual(cases, [])

    def test_generate_edge_cases_str(self):
        gen = TestCaseGenerator()
        edges = gen.generate_edge_cases([("name", "str")])
        self.assertGreater(len(edges), 0)
        self.assertIn("name", edges[0])

    def test_generate_edge_cases_no_params(self):
        gen = TestCaseGenerator()
        edges = gen.generate_edge_cases([])
        self.assertEqual(edges, [{}])

    def test_to_code(self):
        cases = [
            TestCase(name="test_add_0", function_name="add", inputs={"a": 0, "b": 0}, expected=0),
        ]
        gen = TestCaseGenerator()
        code = gen.to_code(cases)
        self.assertIn("class TestGenerated", code)
        self.assertIn("def test_add_0", code)
        self.assertIn("assertEqual", code)

    def test_to_code_empty(self):
        gen = TestCaseGenerator()
        code = gen.to_code([])
        self.assertIn("class TestGenerated", code)
        self.assertIn("pass", code)

    def test_to_code_custom_class(self):
        cases = [TestCase(name="test_x", function_name="x")]
        gen = TestCaseGenerator()
        code = gen.to_code(cases, class_name="TestCustom")
        self.assertIn("class TestCustom", code)

    def test_add_pattern(self):
        gen = TestCaseGenerator()
        gen.add_pattern("Color", ["red", "green", "blue"])
        edges = gen.generate_edge_cases([("c", "Color")])
        values = [e["c"] for e in edges]
        self.assertIn("red", values)

    def test_generate_filter_function(self):
        src = "def foo(): pass\ndef bar(): pass\n"
        gen = TestCaseGenerator()
        cases = gen.generate(src, "foo")
        self.assertTrue(all(c.function_name == "foo" for c in cases))


class TestEdgeCaseValues(unittest.TestCase):
    def test_int_edges(self):
        gen = TestCaseGenerator()
        edges = gen.generate_edge_cases([("n", "int")])
        values = [e["n"] for e in edges]
        self.assertIn(0, values)
        self.assertIn(-1, values)

    def test_float_edges(self):
        gen = TestCaseGenerator()
        edges = gen.generate_edge_cases([("x", "float")])
        values = [e["x"] for e in edges]
        self.assertIn(0.0, values)

    def test_unknown_hint_fallback(self):
        gen = TestCaseGenerator()
        edges = gen.generate_edge_cases([("x", "SomeCustomType")])
        self.assertGreater(len(edges), 0)


if __name__ == "__main__":
    unittest.main()
