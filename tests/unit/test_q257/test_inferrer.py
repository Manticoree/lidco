"""Tests for lidco.types.inferrer — TypeInferrer."""
from __future__ import annotations

import unittest

from lidco.types.inferrer import InferredType, TypeInferrer


class TestInferredType(unittest.TestCase):
    def test_frozen(self):
        it = InferredType(name="x", type="int", confidence=0.9)
        with self.assertRaises(AttributeError):
            it.name = "y"  # type: ignore[misc]

    def test_defaults(self):
        it = InferredType(name="x", type="str", confidence=0.8)
        self.assertEqual(it.source, "usage")


class TestInferFromAssignment(unittest.TestCase):
    def setUp(self):
        self.inf = TypeInferrer()

    def test_int_literal(self):
        r = self.inf.infer_from_assignment("x = 5")
        self.assertIsNotNone(r)
        self.assertEqual(r.name, "x")
        self.assertEqual(r.type, "int")
        self.assertGreater(r.confidence, 0.8)

    def test_float_literal(self):
        r = self.inf.infer_from_assignment("y = 3.14")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "float")

    def test_string_literal(self):
        r = self.inf.infer_from_assignment('name = "hello"')
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "str")

    def test_fstring(self):
        r = self.inf.infer_from_assignment('msg = f"hi {x}"')
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "str")

    def test_bytes_literal(self):
        r = self.inf.infer_from_assignment('data = b"raw"')
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "bytes")

    def test_bool_true(self):
        r = self.inf.infer_from_assignment("flag = True")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "bool")

    def test_bool_false(self):
        r = self.inf.infer_from_assignment("flag = False")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "bool")

    def test_none_literal(self):
        r = self.inf.infer_from_assignment("val = None")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "None")

    def test_empty_list(self):
        r = self.inf.infer_from_assignment("items = []")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "list")

    def test_list_with_elements(self):
        r = self.inf.infer_from_assignment("items = [1, 2, 3]")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "list")

    def test_empty_dict(self):
        r = self.inf.infer_from_assignment("d = {}")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "dict")

    def test_set_call(self):
        r = self.inf.infer_from_assignment("s = set()")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "set")

    def test_tuple(self):
        r = self.inf.infer_from_assignment("t = ()")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "tuple")

    def test_no_assignment(self):
        r = self.inf.infer_from_assignment("print('hello')")
        self.assertIsNone(r)

    def test_empty_line(self):
        r = self.inf.infer_from_assignment("")
        self.assertIsNone(r)

    def test_builtin_call_int(self):
        r = self.inf.infer_from_assignment("x = int('5')")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "int")

    def test_builtin_call_str(self):
        r = self.inf.infer_from_assignment("s = str(42)")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "str")

    def test_source_is_assignment(self):
        r = self.inf.infer_from_assignment("x = 10")
        self.assertEqual(r.source, "assignment")


class TestInferFromReturn(unittest.TestCase):
    def setUp(self):
        self.inf = TypeInferrer()

    def test_returns_int(self):
        src = "def foo():\n    return 42\n"
        r = self.inf.infer_from_return(src, "foo")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "int")
        self.assertEqual(r.source, "return")

    def test_returns_string(self):
        src = 'def bar():\n    return "hello"\n'
        r = self.inf.infer_from_return(src, "bar")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "str")

    def test_returns_none_implicit(self):
        src = "def baz():\n    pass\n"
        r = self.inf.infer_from_return(src, "baz")
        self.assertIsNotNone(r)
        self.assertEqual(r.type, "None")

    def test_mixed_returns(self):
        src = "def mix():\n    if True:\n        return 1\n    return 'x'\n"
        r = self.inf.infer_from_return(src, "mix")
        self.assertIsNotNone(r)
        self.assertIn("|", r.type)

    def test_unknown_function(self):
        src = "def foo():\n    return 1\n"
        r = self.inf.infer_from_return(src, "nonexistent")
        self.assertIsNone(r)

    def test_syntax_error(self):
        r = self.inf.infer_from_return("def broken(:", "broken")
        self.assertIsNone(r)


class TestInferAll(unittest.TestCase):
    def setUp(self):
        self.inf = TypeInferrer()

    def test_multiple_assignments(self):
        src = "x = 5\ny = 'hello'\n"
        results = self.inf.infer_all(src)
        names = {r.name for r in results}
        self.assertIn("x", names)
        self.assertIn("y", names)

    def test_assignments_and_functions(self):
        src = "count = 0\ndef get_count():\n    return 42\n"
        results = self.inf.infer_all(src)
        names = {r.name for r in results}
        self.assertIn("count", names)
        self.assertIn("get_count", names)

    def test_empty_source(self):
        results = self.inf.infer_all("")
        self.assertEqual(results, [])

    def test_no_duplicates(self):
        src = "x = 1\nx = 2\n"
        results = self.inf.infer_all(src)
        x_results = [r for r in results if r.name == "x"]
        self.assertEqual(len(x_results), 1)


class TestConfidenceThreshold(unittest.TestCase):
    def test_default_threshold(self):
        inf = TypeInferrer()
        self.assertEqual(inf.confidence_threshold, 0.5)

    def test_custom_threshold(self):
        inf = TypeInferrer(confidence_threshold=0.99)
        self.assertEqual(inf.confidence_threshold, 0.99)
        # High threshold filters out lower-confidence results.
        r = inf.infer_from_assignment("x = None")
        self.assertIsNone(r)  # None inference has 0.85 confidence


if __name__ == "__main__":
    unittest.main()
