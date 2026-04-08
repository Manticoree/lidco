"""Tests for ExceptionChainAnalyzer (Q342, Task 1)."""
from __future__ import annotations

import unittest

from lidco.stability.exception_chain import ExceptionChainAnalyzer


class TestTracePropagation(unittest.TestCase):
    def setUp(self):
        self.analyzer = ExceptionChainAnalyzer()

    def test_caught_exception_detected(self):
        src = """\
try:
    risky()
except ValueError:
    pass
"""
        results = self.analyzer.trace_propagation(src)
        actions = [r["action"] for r in results]
        self.assertIn("caught", actions)

    def test_caught_has_correct_exception_type(self):
        src = """\
try:
    risky()
except TypeError as e:
    pass
"""
        results = self.analyzer.trace_propagation(src)
        types = [r["exception_type"] for r in results]
        self.assertIn("TypeError", types)

    def test_raise_inside_handler_is_raised(self):
        src = """\
try:
    risky()
except ValueError:
    raise RuntimeError("wrapped")
"""
        results = self.analyzer.trace_propagation(src)
        actions = [r["action"] for r in results]
        self.assertIn("raised", actions)

    def test_bare_reraise_detected(self):
        src = """\
try:
    risky()
except ValueError:
    raise
"""
        results = self.analyzer.trace_propagation(src)
        actions = [r["action"] for r in results]
        self.assertIn("reraised", actions)

    def test_no_try_returns_empty(self):
        src = "x = 1\n"
        results = self.analyzer.trace_propagation(src)
        self.assertEqual(results, [])

    def test_syntax_error_returns_empty(self):
        results = self.analyzer.trace_propagation("def (:")
        self.assertEqual(results, [])


class TestFindUnhandled(unittest.TestCase):
    def setUp(self):
        self.analyzer = ExceptionChainAnalyzer()

    def test_raise_outside_try_detected(self):
        src = """\
def foo():
    raise ValueError("oops")
"""
        results = self.analyzer.find_unhandled(src)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["line"], 2)

    def test_raise_inside_try_not_in_unhandled(self):
        src = """\
try:
    raise ValueError("inside try")
except ValueError:
    pass
"""
        results = self.analyzer.find_unhandled(src)
        self.assertEqual(results, [])

    def test_context_is_function_name(self):
        src = """\
def my_func():
    raise RuntimeError("bad")
"""
        results = self.analyzer.find_unhandled(src)
        self.assertEqual(results[0]["context"], "my_func")

    def test_exception_type_captured(self):
        src = "raise KeyError('x')\n"
        results = self.analyzer.find_unhandled(src)
        self.assertIn("KeyError", results[0]["exception_type"])

    def test_syntax_error_returns_empty(self):
        results = self.analyzer.find_unhandled("def (:")
        self.assertEqual(results, [])


class TestAuditCatchAll(unittest.TestCase):
    def setUp(self):
        self.analyzer = ExceptionChainAnalyzer()

    def test_bare_except_is_high(self):
        src = """\
try:
    pass
except:
    pass
"""
        results = self.analyzer.audit_catch_all(src)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["severity"], "HIGH")

    def test_bare_except_pattern_label(self):
        src = """\
try:
    pass
except:
    pass
"""
        results = self.analyzer.audit_catch_all(src)
        self.assertIn("bare except", results[0]["pattern"])

    def test_except_exception_swallowed_is_medium(self):
        src = """\
try:
    risky()
except Exception:
    pass
"""
        results = self.analyzer.audit_catch_all(src)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["severity"], "MEDIUM")

    def test_except_exception_with_reraise_not_flagged(self):
        src = """\
try:
    risky()
except Exception:
    raise
"""
        results = self.analyzer.audit_catch_all(src)
        self.assertEqual(results, [])

    def test_specific_exception_not_flagged(self):
        src = """\
try:
    risky()
except ValueError:
    pass
"""
        results = self.analyzer.audit_catch_all(src)
        self.assertEqual(results, [])


class TestCheckChainCompleteness(unittest.TestCase):
    def setUp(self):
        self.analyzer = ExceptionChainAnalyzer()

    def test_raise_without_from_flagged(self):
        src = """\
try:
    risky()
except ValueError as e:
    raise RuntimeError("wrapped")
"""
        results = self.analyzer.check_chain_completeness(src)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["has_from"])

    def test_raise_with_from_not_flagged(self):
        src = """\
try:
    risky()
except ValueError as e:
    raise RuntimeError("wrapped") from e
"""
        results = self.analyzer.check_chain_completeness(src)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["has_from"])

    def test_suggestion_present_when_missing_from(self):
        src = """\
try:
    risky()
except ValueError as e:
    raise RuntimeError("wrapped")
"""
        results = self.analyzer.check_chain_completeness(src)
        self.assertIn("from", results[0]["suggestion"])

    def test_no_raises_returns_empty(self):
        src = """\
try:
    x = 1
except ValueError:
    x = 0
"""
        results = self.analyzer.check_chain_completeness(src)
        self.assertEqual(results, [])
