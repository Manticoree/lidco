"""Tests for lidco.verify.code_proof — CodeProofChecker."""
from __future__ import annotations

import unittest

from lidco.verify.code_proof import CodeProofChecker, ProofResult


class TestCodeProofChecker(unittest.TestCase):
    def setUp(self):
        self.c = CodeProofChecker()

    # -- check_precondition -----------------------------------------------

    def test_precondition_present(self):
        func = "def foo(x):\n    assert x > 0\n    return x * 2"
        self.assertTrue(self.c.check_precondition(func, "assert"))

    def test_precondition_absent(self):
        func = "def foo(x):\n    return x"
        self.assertFalse(self.c.check_precondition(func, "validates input thoroughly"))

    def test_precondition_keyword_match(self):
        func = "def foo(x):\n    if not isinstance(x, int):\n        raise TypeError"
        self.assertTrue(self.c.check_precondition(func, "isinstance check"))

    # -- check_postcondition ----------------------------------------------

    def test_postcondition_exact_match(self):
        func = "def foo(x):\n    return x > 0"
        self.assertTrue(self.c.check_postcondition(func, "return"))

    def test_postcondition_keyword_partial(self):
        func = "def compute(data):\n    result = process(data)\n    return result"
        self.assertTrue(self.c.check_postcondition(func, "result returned"))

    def test_postcondition_no_match(self):
        func = "def foo():\n    pass"
        self.assertFalse(self.c.check_postcondition(func, "database committed successfully"))

    # -- check_invariant --------------------------------------------------

    def test_invariant_holds(self):
        before = "class Foo:\n    count = 0"
        after = "class Foo:\n    count = 0\n    name = ''"
        self.assertTrue(self.c.check_invariant(before, after, "class Foo count"))

    def test_invariant_broken(self):
        before = "class Foo:\n    count = 0"
        after = "class Bar:\n    name = ''"
        self.assertFalse(self.c.check_invariant(before, after, "count preserved"))

    # -- verify_change ----------------------------------------------------

    def test_valid_change(self):
        old = "def foo():\n    return 1"
        new = "def foo():\n    return 2"
        result = self.c.verify_change(old, new)
        self.assertIsInstance(result, ProofResult)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.preconditions_met)
        self.assertTrue(result.postconditions_met)
        self.assertTrue(result.invariants_held)

    def test_syntax_error_in_new(self):
        old = "def foo():\n    return 1"
        new = "def foo(\n    return 1"
        result = self.c.verify_change(old, new)
        self.assertFalse(result.is_valid)
        self.assertIn("syntax", result.issues[0].lower())

    def test_removed_name_reported(self):
        old = "def foo():\n    pass\ndef bar():\n    pass"
        new = "def foo():\n    pass"
        result = self.c.verify_change(old, new)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("bar" in i for i in result.issues))

    def test_proof_result_frozen(self):
        r = ProofResult(is_valid=True, preconditions_met=True, postconditions_met=True, invariants_held=True)
        with self.assertRaises(AttributeError):
            r.is_valid = False  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
