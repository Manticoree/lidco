"""Tests for GracefulDegradationChecker (Q342, Task 3)."""
from __future__ import annotations

import unittest

from lidco.stability.degradation import GracefulDegradationChecker


class TestCheckFallbacks(unittest.TestCase):
    def setUp(self):
        self.checker = GracefulDegradationChecker()

    def test_pass_only_handler_has_no_fallback(self):
        src = """\
try:
    optional_feature()
except Exception:
    pass
"""
        results = self.checker.check_fallbacks(src)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["has_fallback"])

    def test_assignment_in_handler_is_fallback(self):
        src = """\
try:
    result = optional_feature()
except Exception:
    result = default_value
"""
        results = self.checker.check_fallbacks(src)
        self.assertTrue(results[0]["has_fallback"])

    def test_return_in_handler_is_fallback(self):
        src = """\
try:
    x = compute()
except Exception:
    return None
"""
        results = self.checker.check_fallbacks(src)
        self.assertTrue(results[0]["has_fallback"])

    def test_suggestion_present_when_no_fallback(self):
        src = """\
try:
    risky()
except Exception:
    pass
"""
        results = self.checker.check_fallbacks(src)
        self.assertIn("fallback", results[0]["suggestion"].lower())

    def test_no_try_returns_empty(self):
        results = self.checker.check_fallbacks("x = 1\n")
        self.assertEqual(results, [])

    def test_syntax_error_returns_empty(self):
        results = self.checker.check_fallbacks("def (:")
        self.assertEqual(results, [])


class TestCheckOptionalDeps(unittest.TestCase):
    def setUp(self):
        self.checker = GracefulDegradationChecker()

    def test_correct_import_fallback_detected(self):
        src = """\
try:
    import PIL
except ImportError:
    PIL = None
"""
        results = self.checker.check_optional_deps(src)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["has_fallback"])
        self.assertTrue(results[0]["fallback_correct"])

    def test_import_without_fallback_flagged(self):
        src = """\
try:
    import PIL
except Exception:
    pass
"""
        results = self.checker.check_optional_deps(src)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["fallback_correct"])

    def test_module_name_captured(self):
        src = """\
try:
    import numpy
except ImportError:
    numpy = None
"""
        results = self.checker.check_optional_deps(src)
        self.assertEqual(results[0]["module"], "numpy")

    def test_no_import_in_try_returns_empty(self):
        src = """\
try:
    x = 1
except ValueError:
    x = 0
"""
        results = self.checker.check_optional_deps(src)
        self.assertEqual(results, [])


class TestCheckNetworkResilience(unittest.TestCase):
    def setUp(self):
        self.checker = GracefulDegradationChecker()

    def test_request_without_timeout_flagged(self):
        src = "resp = requests.get('http://example.com')\n"
        results = self.checker.check_network_resilience(src)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["has_timeout"])

    def test_request_with_timeout_ok(self):
        src = "resp = requests.get('http://example.com', timeout=5)\n"
        results = self.checker.check_network_resilience(src)
        # has_timeout should be True
        matching = [r for r in results if r["call"] == "get"]
        self.assertTrue(matching[0]["has_timeout"])

    def test_suggestion_references_timeout(self):
        src = "resp = requests.post('http://example.com')\n"
        results = self.checker.check_network_resilience(src)
        self.assertIn("timeout", results[0]["suggestion"].lower())

    def test_non_network_call_ignored(self):
        src = "x = process_data(items)\n"
        results = self.checker.check_network_resilience(src)
        self.assertEqual(results, [])


class TestCheckTimeoutBehavior(unittest.TestCase):
    def setUp(self):
        self.checker = GracefulDegradationChecker()

    def test_zero_timeout_flagged(self):
        src = "resp = requests.get('http://x.com', timeout=0)\n"
        results = self.checker.check_timeout_behavior(src)
        self.assertEqual(len(results), 1)
        self.assertIn("0", results[0]["suggestion"])

    def test_large_timeout_flagged(self):
        src = "resp = requests.get('http://x.com', timeout=600)\n"
        results = self.checker.check_timeout_behavior(src)
        self.assertEqual(len(results), 1)
        self.assertIn("large", results[0]["suggestion"].lower())

    def test_reasonable_timeout_no_suggestion(self):
        src = "resp = requests.get('http://x.com', timeout=30)\n"
        results = self.checker.check_timeout_behavior(src)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["suggestion"], "")

    def test_timeout_value_captured(self):
        src = "resp = requests.get('http://x.com', timeout=10)\n"
        results = self.checker.check_timeout_behavior(src)
        self.assertEqual(results[0]["timeout_value"], "10")

    def test_no_timeout_kwarg_no_results(self):
        src = "resp = requests.get('http://x.com')\n"
        results = self.checker.check_timeout_behavior(src)
        self.assertEqual(results, [])
