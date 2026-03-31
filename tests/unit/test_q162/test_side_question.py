"""Tests for lidco.session.side_question — Q162 Task 922."""
from __future__ import annotations

import unittest

from lidco.session.side_question import SideQuestionManager, SideQuestionResult


class TestSideQuestionResult(unittest.TestCase):
    def test_dataclass_fields(self) -> None:
        r = SideQuestionResult(question="hi", answer="hello", tokens_used=5)
        self.assertEqual(r.question, "hi")
        self.assertEqual(r.answer, "hello")
        self.assertEqual(r.tokens_used, 5)

    def test_frozen(self) -> None:
        r = SideQuestionResult(question="x", answer="y", tokens_used=1)
        with self.assertRaises(AttributeError):
            r.question = "z"  # type: ignore[misc]


class TestSideQuestionManager(unittest.TestCase):
    def test_ask_returns_result(self) -> None:
        mgr = SideQuestionManager()
        result = mgr.ask("What is 2+2?")
        self.assertIsInstance(result, SideQuestionResult)
        self.assertEqual(result.question, "What is 2+2?")
        self.assertIn("2+2", result.answer)
        self.assertGreater(result.tokens_used, 0)

    def test_ask_empty_question(self) -> None:
        mgr = SideQuestionManager()
        result = mgr.ask("")
        self.assertEqual(result.answer, "No question provided.")
        self.assertEqual(result.tokens_used, 0)

    def test_ask_whitespace_question(self) -> None:
        mgr = SideQuestionManager()
        result = mgr.ask("   ")
        self.assertEqual(result.answer, "No question provided.")

    def test_ask_with_context(self) -> None:
        mgr = SideQuestionManager()
        result = mgr.ask("How?", context="Some background")
        self.assertIsInstance(result, SideQuestionResult)
        self.assertGreater(result.tokens_used, 0)

    def test_history_empty(self) -> None:
        mgr = SideQuestionManager()
        self.assertEqual(mgr.history(), [])

    def test_history_populated(self) -> None:
        mgr = SideQuestionManager()
        mgr.ask("Q1")
        mgr.ask("Q2")
        hist = mgr.history()
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[0].question, "Q1")
        self.assertEqual(hist[1].question, "Q2")

    def test_clear_history(self) -> None:
        mgr = SideQuestionManager()
        mgr.ask("Q1")
        mgr.clear_history()
        self.assertEqual(mgr.history(), [])

    def test_max_history_default(self) -> None:
        mgr = SideQuestionManager()
        self.assertEqual(mgr.max_history, 20)

    def test_max_history_custom(self) -> None:
        mgr = SideQuestionManager(max_history=3)
        self.assertEqual(mgr.max_history, 3)

    def test_history_bounded(self) -> None:
        mgr = SideQuestionManager(max_history=3)
        for i in range(5):
            mgr.ask(f"Q{i}")
        hist = mgr.history()
        self.assertEqual(len(hist), 3)
        # Oldest two should have been evicted
        self.assertEqual(hist[0].question, "Q2")
        self.assertEqual(hist[2].question, "Q4")

    def test_ask_records_in_history(self) -> None:
        mgr = SideQuestionManager()
        result = mgr.ask("test question")
        self.assertIs(mgr.history()[-1], result)

    def test_empty_question_still_recorded(self) -> None:
        mgr = SideQuestionManager()
        mgr.ask("")
        self.assertEqual(len(mgr.history()), 1)


if __name__ == "__main__":
    unittest.main()
