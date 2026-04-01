"""Tests for context.semantic_summarizer — SummaryEntry, SummaryResult, SemanticSummarizer."""
from __future__ import annotations

import unittest

from lidco.context.semantic_summarizer import (
    SemanticSummarizer,
    SummaryEntry,
    SummaryResult,
)


class TestSummaryEntry(unittest.TestCase):
    def test_frozen(self):
        e = SummaryEntry(role="user", content="hi")
        with self.assertRaises(AttributeError):
            e.role = "system"  # type: ignore[misc]

    def test_defaults(self):
        e = SummaryEntry(role="user", content="hello")
        self.assertEqual(e.turn_index, 0)
        self.assertEqual(e.importance, 0.5)

    def test_equality(self):
        a = SummaryEntry(role="user", content="hi", turn_index=1)
        b = SummaryEntry(role="user", content="hi", turn_index=1)
        self.assertEqual(a, b)


class TestSummaryResult(unittest.TestCase):
    def test_frozen(self):
        r = SummaryResult()
        with self.assertRaises(AttributeError):
            r.ratio = 1.0  # type: ignore[misc]

    def test_defaults(self):
        r = SummaryResult()
        self.assertEqual(r.entries, ())
        self.assertEqual(r.original_tokens, 0)
        self.assertEqual(r.compressed_tokens, 0)
        self.assertEqual(r.ratio, 0.0)


class TestSemanticSummarizer(unittest.TestCase):
    def test_empty_turns(self):
        s = SemanticSummarizer()
        result = s.summarize([])
        self.assertEqual(result.entries, ())
        self.assertEqual(result.original_tokens, 0)

    def test_single_system_message(self):
        s = SemanticSummarizer()
        result = s.summarize([{"role": "system", "content": "You are helpful."}])
        self.assertEqual(len(result.entries), 1)
        # System messages kept fully
        self.assertEqual(result.entries[0].content, "You are helpful.")
        self.assertEqual(result.entries[0].importance, 1.0)

    def test_code_preserved(self):
        s = SemanticSummarizer(max_ratio=0.9)
        code_content = "Here is code:\n```python\nprint('hello')\n```\nEnd."
        result = s.summarize([{"role": "assistant", "content": code_content}])
        self.assertIn("```python", result.entries[0].content)

    def test_long_text_compressed(self):
        s = SemanticSummarizer(max_ratio=0.5)
        long_text = "\n".join(f"Line {i}" for i in range(50))
        result = s.summarize([{"role": "assistant", "content": long_text}])
        self.assertLess(len(result.entries[0].content), len(long_text))

    def test_ratio_computed(self):
        s = SemanticSummarizer(max_ratio=0.5)
        turns = [{"role": "assistant", "content": "x" * 200}]
        result = s.summarize(turns)
        self.assertGreater(result.ratio, 0.0)
        self.assertLessEqual(result.ratio, 1.0)

    def test_score_importance_system(self):
        s = SemanticSummarizer()
        self.assertEqual(s.score_importance({"role": "system", "content": "x"}), 1.0)

    def test_score_importance_error(self):
        s = SemanticSummarizer()
        self.assertEqual(s.score_importance({"role": "assistant", "content": "Traceback: error"}), 0.9)

    def test_score_importance_code(self):
        s = SemanticSummarizer()
        self.assertEqual(s.score_importance({"role": "assistant", "content": "```py\n```"}), 0.8)

    def test_score_importance_question(self):
        s = SemanticSummarizer()
        self.assertEqual(s.score_importance({"role": "user", "content": "What is this?"}), 0.7)

    def test_score_importance_short(self):
        s = SemanticSummarizer()
        self.assertEqual(s.score_importance({"role": "assistant", "content": "ok"}), 0.3)

    def test_compress_turn_empty(self):
        s = SemanticSummarizer()
        self.assertEqual(s.compress_turn(""), "")

    def test_stats_initial(self):
        s = SemanticSummarizer()
        stats = s.stats()
        self.assertEqual(stats["original_tokens"], 0)
        self.assertEqual(stats["compressed_tokens"], 0)
        self.assertEqual(stats["max_ratio"], 0.5)


if __name__ == "__main__":
    unittest.main()
