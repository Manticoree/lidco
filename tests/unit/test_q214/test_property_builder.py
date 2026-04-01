"""Tests for test_intel.property_builder — PropertySpec, PropertyBuilder."""
from __future__ import annotations

import unittest

from lidco.test_intel.property_builder import PropertyBuilder, PropertySpec


class TestPropertySpec(unittest.TestCase):
    def test_frozen(self):
        ps = PropertySpec(name="t", function_name="f", property_description="d")
        with self.assertRaises(AttributeError):
            ps.name = "x"  # type: ignore[misc]

    def test_defaults(self):
        ps = PropertySpec(name="t", function_name="f", property_description="d")
        self.assertEqual(ps.input_strategy, "")
        self.assertEqual(ps.invariant, "")

    def test_fields(self):
        ps = PropertySpec(
            name="test_prop",
            function_name="add",
            property_description="commutativity",
            input_strategy="a=integers(), b=integers()",
            invariant="add(a,b) == add(b,a)",
        )
        self.assertEqual(ps.function_name, "add")
        self.assertEqual(ps.property_description, "commutativity")


class TestPropertyBuilder(unittest.TestCase):
    def test_infer_strategy_int(self):
        pb = PropertyBuilder()
        self.assertIn("integers", pb.infer_strategy("int"))

    def test_infer_strategy_str(self):
        pb = PropertyBuilder()
        self.assertIn("text", pb.infer_strategy("str"))

    def test_infer_strategy_unknown(self):
        pb = PropertyBuilder()
        result = pb.infer_strategy("CustomType")
        self.assertIn("None", result)

    def test_build_basic(self):
        pb = PropertyBuilder()
        spec = pb.build("add", [("a", "int"), ("b", "int")])
        self.assertEqual(spec.function_name, "add")
        self.assertIn("integers", spec.input_strategy)
        self.assertIn("add", spec.invariant)

    def test_build_no_params(self):
        pb = PropertyBuilder()
        spec = pb.build("noop", [])
        self.assertEqual(spec.function_name, "noop")
        self.assertIn("no params", spec.input_strategy)

    def test_to_code(self):
        pb = PropertyBuilder()
        spec = pb.build("add", [("a", "int"), ("b", "int")])
        code = pb.to_code(spec)
        self.assertIn("@given", code)
        self.assertIn("def test_prop_add", code)
        self.assertIn("add(", code)

    def test_to_code_includes_invariant(self):
        pb = PropertyBuilder()
        spec = PropertySpec(
            name="test_p",
            function_name="f",
            property_description="desc",
            invariant="some invariant",
        )
        code = pb.to_code(spec)
        self.assertIn("some invariant", code)

    def test_detect_invariants_length(self):
        pb = PropertyBuilder()
        src = "if len(items) > 0:\n    pass\n"
        inv = pb.detect_invariants(src)
        self.assertIn("length constraint", inv)

    def test_detect_invariants_assert(self):
        pb = PropertyBuilder()
        src = "assert x > 0\nassert y is not None\n"
        inv = pb.detect_invariants(src)
        self.assertTrue(any("assertion" in i for i in inv))

    def test_detect_invariants_isinstance(self):
        pb = PropertyBuilder()
        src = "isinstance(val, int)\n"
        inv = pb.detect_invariants(src)
        self.assertIn("type constraint", inv)

    def test_detect_invariants_sorted(self):
        pb = PropertyBuilder()
        src = "result = sorted(data)\n"
        inv = pb.detect_invariants(src)
        self.assertIn("ordering invariant", inv)

    def test_detect_invariants_empty(self):
        pb = PropertyBuilder()
        inv = pb.detect_invariants("x = 1\n")
        self.assertEqual(inv, [])


if __name__ == "__main__":
    unittest.main()
