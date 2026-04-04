"""Tests for lidco.recovery.classifier."""
from __future__ import annotations

import unittest

from lidco.recovery.classifier import ErrorClassification, ErrorClassifier


class TestErrorClassification(unittest.TestCase):
    def test_frozen_dataclass(self):
        ec = ErrorClassification(type="syntax", confidence=0.8, indicators=["SyntaxError"])
        with self.assertRaises(AttributeError):
            ec.type = "runtime"  # type: ignore[misc]

    def test_default_suggestion(self):
        ec = ErrorClassification(type="x", confidence=0.0, indicators=[])
        self.assertEqual(ec.suggestion, "")


class TestErrorClassifier(unittest.TestCase):
    def setUp(self):
        self.clf = ErrorClassifier()

    def test_classify_syntax_error(self):
        result = self.clf.classify("SyntaxError: invalid syntax")
        self.assertEqual(result.type, "syntax")
        self.assertGreater(result.confidence, 0)
        self.assertTrue(len(result.indicators) > 0)

    def test_classify_runtime_error(self):
        result = self.clf.classify("TypeError: unsupported operand")
        self.assertEqual(result.type, "runtime")

    def test_classify_network_error(self):
        result = self.clf.classify("ConnectionRefusedError: [Errno 111] Connection refused")
        self.assertEqual(result.type, "network")

    def test_classify_permission_error(self):
        result = self.clf.classify("PermissionError: [Errno 13] Permission denied")
        self.assertEqual(result.type, "permission")

    def test_classify_resource_error(self):
        result = self.clf.classify("MemoryError: out of memory")
        self.assertEqual(result.type, "resource")

    def test_classify_timeout_error(self):
        result = self.clf.classify("TimeoutError: connection timed out")
        self.assertEqual(result.type, "timeout")

    def test_classify_unknown(self):
        result = self.clf.classify("some totally random message")
        self.assertEqual(result.type, "unknown")
        self.assertEqual(result.confidence, 0.0)

    def test_classify_exception(self):
        result = self.clf.classify_exception("KeyError", "'missing_key'")
        self.assertEqual(result.type, "runtime")

    def test_add_pattern(self):
        self.clf.add_pattern("custom", r"CustomBoom")
        result = self.clf.classify("CustomBoom happened")
        self.assertEqual(result.type, "custom")

    def test_patterns_property(self):
        pats = self.clf.patterns
        self.assertIn("syntax", pats)
        self.assertIn("runtime", pats)

    def test_summary(self):
        s = self.clf.summary()
        self.assertIn("error_types", s)
        self.assertIn("total_patterns", s)
        self.assertGreater(s["total_patterns"], 0)

    def test_classify_with_traceback(self):
        result = self.clf.classify("error", traceback="File test.py line 5\nSyntaxError: invalid syntax")
        self.assertEqual(result.type, "syntax")


if __name__ == "__main__":
    unittest.main()
