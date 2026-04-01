"""Tests for intent_classifier module."""
from __future__ import annotations

import unittest

from lidco.understanding.intent_classifier import (
    ClassifiedIntent,
    IntentClassifier,
    IntentType,
)


class TestIntentType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(IntentType.FIND, "find")
        self.assertEqual(IntentType.UNKNOWN, "unknown")


class TestClassifiedIntent(unittest.TestCase):
    def test_frozen(self):
        ci = ClassifiedIntent(intent=IntentType.FIND, confidence=0.8)
        with self.assertRaises(AttributeError):
            ci.confidence = 0.5  # type: ignore[misc]

    def test_defaults(self):
        ci = ClassifiedIntent(intent=IntentType.FIND, confidence=0.8)
        self.assertIsNone(ci.secondary_intent)
        self.assertEqual(ci.raw_query, "")


class TestIntentClassifier(unittest.TestCase):
    def setUp(self):
        self.clf = IntentClassifier()

    def test_classify_find(self):
        result = self.clf.classify("find the function that handles auth")
        self.assertEqual(result.intent, IntentType.FIND)
        self.assertGreater(result.confidence, 0)

    def test_classify_explain(self):
        result = self.clf.classify("explain how this class works")
        self.assertEqual(result.intent, IntentType.EXPLAIN)

    def test_classify_refactor(self):
        result = self.clf.classify("refactor this function to simplify it")
        self.assertEqual(result.intent, IntentType.REFACTOR)

    def test_classify_fix(self):
        result = self.clf.classify("fix the bug in the parser")
        self.assertEqual(result.intent, IntentType.FIX)

    def test_classify_generate(self):
        result = self.clf.classify("generate a new test file")
        self.assertEqual(result.intent, IntentType.GENERATE)

    def test_classify_unknown(self):
        result = self.clf.classify("xyzzy foobar baz")
        self.assertEqual(result.intent, IntentType.UNKNOWN)
        self.assertEqual(result.confidence, 0.0)

    def test_confidence_range(self):
        result = self.clf.classify("find search locate where")
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)

    def test_add_pattern(self):
        self.clf.add_pattern(IntentType.FIND, ["discover", "pinpoint"])
        result = self.clf.classify("discover the module")
        self.assertEqual(result.intent, IntentType.FIND)

    def test_list_patterns(self):
        patterns = self.clf.list_patterns()
        self.assertIn("find", patterns)
        self.assertIn("explain", patterns)
        self.assertIsInstance(patterns["find"], list)


if __name__ == "__main__":
    unittest.main()
