"""Tests for ContinuationConfig and should_continue (Task 918)."""
from __future__ import annotations

import unittest

from lidco.llm.continuation_config import ContinuationConfig, should_continue


class TestContinuationConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = ContinuationConfig()
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.max_continuations, 5)
        self.assertTrue(cfg.detect_code_truncation)

    def test_custom_values(self):
        cfg = ContinuationConfig(enabled=False, max_continuations=10, detect_code_truncation=False)
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.max_continuations, 10)
        self.assertFalse(cfg.detect_code_truncation)


class TestShouldContinue(unittest.TestCase):
    def test_disabled_returns_false(self):
        cfg = ContinuationConfig(enabled=False)
        self.assertFalse(should_continue("some text...", cfg))

    def test_empty_response_returns_false(self):
        cfg = ContinuationConfig()
        self.assertFalse(should_continue("", cfg))

    def test_whitespace_returns_false(self):
        cfg = ContinuationConfig()
        self.assertFalse(should_continue("   ", cfg))

    def test_ellipsis_marker(self):
        cfg = ContinuationConfig()
        self.assertTrue(should_continue("code here...", cfg))

    def test_hash_continued_marker(self):
        cfg = ContinuationConfig()
        self.assertTrue(should_continue("def foo():\n    # continued", cfg))

    def test_slash_continued_marker(self):
        cfg = ContinuationConfig()
        self.assertTrue(should_continue("function foo() {\n// continued", cfg))

    def test_unbalanced_braces_detected(self):
        cfg = ContinuationConfig()
        self.assertTrue(should_continue("if True {\n    x = 1", cfg))

    def test_unbalanced_detection_disabled(self):
        cfg = ContinuationConfig(detect_code_truncation=False)
        self.assertFalse(should_continue("if True {\n    x = 1", cfg))

    def test_balanced_code_no_continue(self):
        cfg = ContinuationConfig()
        self.assertFalse(should_continue("def foo():\n    return 1", cfg))


if __name__ == "__main__":
    unittest.main()
