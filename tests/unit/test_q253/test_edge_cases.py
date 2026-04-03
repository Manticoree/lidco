"""Tests for EdgeCaseGenerator (Q253)."""
from __future__ import annotations

import math
import unittest

from lidco.testgen.edge_cases import EdgeCase, EdgeCaseGenerator


class TestEdgeCase(unittest.TestCase):
    def test_frozen(self):
        ec = EdgeCase(input_value=0, description="zero", category="boundary")
        with self.assertRaises(AttributeError):
            ec.input_value = 1  # type: ignore[misc]

    def test_fields(self):
        ec = EdgeCase(input_value="x", description="d", category="c")
        self.assertEqual(ec.input_value, "x")
        self.assertEqual(ec.description, "d")
        self.assertEqual(ec.category, "c")


class TestForType(unittest.TestCase):
    def setUp(self):
        self.gen = EdgeCaseGenerator()

    def test_int(self):
        cases = self.gen.for_type("int")
        self.assertTrue(len(cases) > 0)
        values = [ec.input_value for ec in cases]
        self.assertIn(0, values)
        self.assertIn(-1, values)

    def test_str(self):
        cases = self.gen.for_type("str")
        self.assertTrue(len(cases) > 0)
        values = [ec.input_value for ec in cases]
        self.assertIn("", values)

    def test_list(self):
        cases = self.gen.for_type("list")
        self.assertTrue(len(cases) > 0)
        values = [ec.input_value for ec in cases]
        self.assertIn([], values)

    def test_dict(self):
        cases = self.gen.for_type("dict")
        self.assertTrue(len(cases) > 0)

    def test_float(self):
        cases = self.gen.for_type("float")
        self.assertTrue(len(cases) > 0)
        values = [ec.input_value for ec in cases]
        self.assertTrue(any(math.isinf(v) for v in values if isinstance(v, float)))

    def test_bool(self):
        cases = self.gen.for_type("bool")
        self.assertEqual(len(cases), 2)

    def test_unknown_type(self):
        cases = self.gen.for_type("unknown")
        self.assertEqual(cases, [])


class TestForFunction(unittest.TestCase):
    def setUp(self):
        self.gen = EdgeCaseGenerator()

    def test_basic(self):
        params = [{"name": "x", "type": "int"}, {"name": "s", "type": "str"}]
        result = self.gen.for_function(params)
        self.assertEqual(len(result), 2)
        self.assertTrue(len(result[0]) > 0)
        self.assertTrue(len(result[1]) > 0)

    def test_empty_params(self):
        result = self.gen.for_function([])
        self.assertEqual(result, [])

    def test_defaults_to_str(self):
        params = [{"name": "val"}]
        result = self.gen.for_function(params)
        self.assertEqual(len(result), 1)
        # Should return str edge cases
        values = [ec.input_value for ec in result[0]]
        self.assertIn("", values)


class TestBoundaryValues(unittest.TestCase):
    def setUp(self):
        self.gen = EdgeCaseGenerator()

    def test_basic_range(self):
        values = self.gen.boundary_values(0, 100)
        self.assertIn(-1, values)
        self.assertIn(0, values)
        self.assertIn(1, values)
        self.assertIn(99, values)
        self.assertIn(100, values)
        self.assertIn(101, values)
        self.assertIn(50, values)  # midpoint

    def test_sorted(self):
        values = self.gen.boundary_values(10, 20)
        self.assertEqual(values, sorted(values))

    def test_narrow_range(self):
        values = self.gen.boundary_values(5, 6)
        self.assertIn(4, values)
        self.assertIn(5, values)
        self.assertIn(6, values)
        self.assertIn(7, values)

    def test_negative_range(self):
        values = self.gen.boundary_values(-10, -5)
        self.assertIn(-11, values)
        self.assertIn(-10, values)
        self.assertIn(-5, values)
        self.assertIn(-4, values)


class TestCategories(unittest.TestCase):
    def test_returns_list(self):
        gen = EdgeCaseGenerator()
        cats = gen.categories()
        self.assertIsInstance(cats, list)
        self.assertTrue(len(cats) > 0)

    def test_contains_boundary(self):
        gen = EdgeCaseGenerator()
        cats = gen.categories()
        self.assertIn("boundary", cats)

    def test_sorted(self):
        gen = EdgeCaseGenerator()
        cats = gen.categories()
        self.assertEqual(cats, sorted(cats))


if __name__ == "__main__":
    unittest.main()
