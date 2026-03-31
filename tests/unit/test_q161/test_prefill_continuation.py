"""Tests for PrefillContinuationEngine (Task 917)."""
from __future__ import annotations

import unittest

from lidco.llm.prefill_continuation import (
    ContinuationResult,
    PrefillContinuationEngine,
)


class TestContinuationResult(unittest.TestCase):
    def test_dataclass_fields(self):
        r = ContinuationResult(full_text="hi", continuations=2, truncated=False, total_tokens=10)
        self.assertEqual(r.full_text, "hi")
        self.assertEqual(r.continuations, 2)
        self.assertFalse(r.truncated)
        self.assertEqual(r.total_tokens, 10)


class TestIsTruncated(unittest.TestCase):
    def setUp(self):
        self.engine = PrefillContinuationEngine()

    def test_empty_text_not_truncated(self):
        self.assertFalse(self.engine.is_truncated(""))

    def test_whitespace_not_truncated(self):
        self.assertFalse(self.engine.is_truncated("   \n  "))

    def test_ellipsis_marker(self):
        self.assertTrue(self.engine.is_truncated("some code here..."))

    def test_continued_marker(self):
        self.assertTrue(self.engine.is_truncated("def foo():\n    # continued"))

    def test_unbalanced_open_paren(self):
        self.assertTrue(self.engine.is_truncated("def foo(a, b,"))

    def test_unbalanced_open_brace(self):
        self.assertTrue(self.engine.is_truncated("if True {\n    x = 1"))

    def test_balanced_not_truncated(self):
        self.assertFalse(self.engine.is_truncated("def foo(a, b):\n    return a + b"))

    def test_custom_markers(self):
        engine = PrefillContinuationEngine(truncation_markers=["CUTOFF"])
        self.assertTrue(engine.is_truncated("some text CUTOFF"))
        self.assertFalse(engine.is_truncated("some text..."))


class TestBuildContinuationPrompt(unittest.TestCase):
    def test_contains_original_and_partial(self):
        engine = PrefillContinuationEngine()
        prompt = engine.build_continuation_prompt("Write code", "def foo(")
        self.assertIn("Write code", prompt)
        self.assertIn("def foo(", prompt)
        self.assertIn("Continue exactly", prompt)


class TestMergeResponses(unittest.TestCase):
    def setUp(self):
        self.engine = PrefillContinuationEngine()

    def test_empty_list(self):
        self.assertEqual(self.engine.merge_responses([]), "")

    def test_single_response(self):
        self.assertEqual(self.engine.merge_responses(["hello"]), "hello")

    def test_no_overlap(self):
        result = self.engine.merge_responses(["abc", "def"])
        self.assertEqual(result, "abcdef")

    def test_with_overlap(self):
        result = self.engine.merge_responses(["hello world", "world goodbye"])
        self.assertEqual(result, "hello world goodbye")


class TestProcess(unittest.TestCase):
    def test_no_continuation_needed(self):
        engine = PrefillContinuationEngine()

        def gen(prompt: str) -> str:
            return "def foo():\n    return 42"

        result = engine.process(gen, "write a function")
        self.assertEqual(result.continuations, 0)
        self.assertFalse(result.truncated)
        self.assertIn("return 42", result.full_text)

    def test_single_continuation(self):
        engine = PrefillContinuationEngine(max_continuations=3)
        call_count = 0

        def gen(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "def foo(a, b,"
            return "c):\n    return a + b + c"

        result = engine.process(gen, "write a function")
        self.assertEqual(result.continuations, 1)
        self.assertFalse(result.truncated)

    def test_max_continuations_reached(self):
        engine = PrefillContinuationEngine(max_continuations=2)

        def gen(prompt: str) -> str:
            return "code with open brace {"

        result = engine.process(gen, "write code")
        self.assertEqual(result.continuations, 2)
        self.assertTrue(result.truncated)

    def test_total_tokens_accumulated(self):
        engine = PrefillContinuationEngine(max_continuations=1)
        call_count = 0

        def gen(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "open brace {"
            return "} closed"

        result = engine.process(gen, "prompt")
        self.assertGreater(result.total_tokens, 0)


class TestFindOverlap(unittest.TestCase):
    def test_no_overlap(self):
        self.assertEqual(PrefillContinuationEngine._find_overlap("abc", "xyz"), 0)

    def test_full_overlap(self):
        self.assertEqual(PrefillContinuationEngine._find_overlap("abc", "abc"), 3)

    def test_partial_overlap(self):
        self.assertEqual(PrefillContinuationEngine._find_overlap("abcd", "cdef"), 2)


if __name__ == "__main__":
    unittest.main()
