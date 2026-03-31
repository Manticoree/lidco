"""Tests for IntentClassifier — Q176."""
from __future__ import annotations

import unittest

from lidco.input.intent_classifier import IntentClassifier, IntentResult, IntentType


class TestIntentClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = IntentClassifier()

    # --- Edit intent ---
    def test_classify_fix_bug(self):
        result = self.classifier.classify("fix the bug in auth.py")
        self.assertEqual(result.intent, IntentType.EDIT)
        self.assertGreater(result.confidence, 0.5)

    def test_classify_change_to(self):
        result = self.classifier.classify("change the color to red")
        self.assertEqual(result.intent, IntentType.EDIT)

    def test_classify_update(self):
        result = self.classifier.classify("update the version number")
        self.assertEqual(result.intent, IntentType.EDIT)

    def test_classify_delete(self):
        result = self.classifier.classify("delete the unused import")
        self.assertEqual(result.intent, IntentType.EDIT)

    # --- Ask intent ---
    def test_classify_question_mark(self):
        result = self.classifier.classify("is this correct?")
        self.assertIn(result.intent, (IntentType.ASK,))

    def test_classify_what_is(self):
        result = self.classifier.classify("what is the return type")
        self.assertEqual(result.intent, IntentType.ASK)

    def test_classify_how_question(self):
        result = self.classifier.classify("how do I use this API?")
        self.assertEqual(result.intent, IntentType.ASK)

    # --- Debug intent ---
    def test_classify_debug(self):
        result = self.classifier.classify("debug the segfault in main.py")
        self.assertEqual(result.intent, IntentType.DEBUG)

    def test_classify_error(self):
        result = self.classifier.classify("there's an error in the output")
        self.assertEqual(result.intent, IntentType.DEBUG)

    def test_classify_not_working(self):
        result = self.classifier.classify("the parser is not working")
        self.assertEqual(result.intent, IntentType.DEBUG)

    # --- Generate intent ---
    def test_classify_create_a(self):
        result = self.classifier.classify("create a new REST API endpoint")
        self.assertEqual(result.intent, IntentType.GENERATE)

    def test_classify_write_a(self):
        result = self.classifier.classify("write a unit test for auth")
        self.assertEqual(result.intent, IntentType.GENERATE)

    def test_classify_scaffold(self):
        result = self.classifier.classify("scaffold a new Flask app")
        self.assertEqual(result.intent, IntentType.GENERATE)

    # --- Refactor intent ---
    def test_classify_refactor(self):
        result = self.classifier.classify("refactor the database layer")
        self.assertEqual(result.intent, IntentType.REFACTOR)
        self.assertGreaterEqual(result.confidence, 0.9)

    def test_classify_simplify(self):
        result = self.classifier.classify("simplify this complex function")
        self.assertEqual(result.intent, IntentType.REFACTOR)

    def test_classify_extract(self):
        result = self.classifier.classify("extract this into a helper")
        self.assertEqual(result.intent, IntentType.REFACTOR)

    # --- Explain intent ---
    def test_classify_explain(self):
        result = self.classifier.classify("explain how the cache works")
        self.assertEqual(result.intent, IntentType.EXPLAIN)

    def test_classify_walk_through(self):
        result = self.classifier.classify("walk me through the pipeline")
        self.assertEqual(result.intent, IntentType.EXPLAIN)

    # --- Edge cases ---
    def test_classify_empty_string(self):
        result = self.classifier.classify("")
        self.assertEqual(result.intent, IntentType.UNKNOWN)
        self.assertEqual(result.confidence, 0.0)

    def test_classify_none_like_whitespace(self):
        result = self.classifier.classify("   ")
        self.assertEqual(result.intent, IntentType.UNKNOWN)

    def test_classify_gibberish(self):
        result = self.classifier.classify("xyzzy plugh")
        self.assertEqual(result.intent, IntentType.UNKNOWN)

    def test_suggested_command_edit(self):
        result = self.classifier.classify("fix the typo")
        self.assertEqual(result.suggested_command, "/edit")

    def test_suggested_command_refactor(self):
        result = self.classifier.classify("refactor the module")
        self.assertEqual(result.suggested_command, "/refactor")

    def test_classify_all_returns_list(self):
        results = self.classifier.classify_all("fix the bug")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_classify_all_empty(self):
        results = self.classifier.classify_all("")
        self.assertEqual(results, [])

    def test_classify_all_sorted_by_confidence(self):
        results = self.classifier.classify_all("fix the error in the code")
        if len(results) > 1:
            for i in range(len(results) - 1):
                self.assertGreaterEqual(results[i].confidence, results[i + 1].confidence)

    def test_intent_result_confidence_clamped(self):
        # Confidence should be clamped to [0, 1]
        r = IntentResult(intent=IntentType.EDIT, confidence=1.5)
        self.assertLessEqual(r.confidence, 1.0)

    def test_intent_result_frozen(self):
        r = IntentResult(intent=IntentType.ASK, confidence=0.8)
        with self.assertRaises(AttributeError):
            r.intent = IntentType.EDIT  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
