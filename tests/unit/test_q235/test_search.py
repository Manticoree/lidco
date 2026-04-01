"""Tests for thinkback.search."""
from __future__ import annotations

import unittest

from lidco.thinkback.search import ThinkingSearch, SearchResult


class TestSearchResult(unittest.TestCase):
    def test_frozen(self) -> None:
        sr = SearchResult(turn=1, line=1, text="x")
        with self.assertRaises(AttributeError):
            sr.turn = 2  # type: ignore[misc]

    def test_defaults(self) -> None:
        sr = SearchResult(turn=0, line=0, text="")
        self.assertAlmostEqual(sr.score, 1.0)
        self.assertEqual(sr.context, "")


class TestThinkingSearch(unittest.TestCase):
    def setUp(self) -> None:
        self.searcher = ThinkingSearch()
        self.blocks = [
            {"turn": 1, "content": "I think Python is great\nJava is also good"},
            {"turn": 2, "content": "Let me try Rust\nPython again here"},
            {"turn": 3, "content": "No matches in this block"},
        ]

    def test_search_basic(self) -> None:
        results = self.searcher.search(self.blocks, "Python")
        self.assertEqual(len(results), 2)
        turns = {r.turn for r in results}
        self.assertIn(1, turns)
        self.assertIn(2, turns)

    def test_search_case_insensitive(self) -> None:
        results = self.searcher.search(self.blocks, "python")
        self.assertEqual(len(results), 2)

    def test_search_no_match(self) -> None:
        results = self.searcher.search(self.blocks, "Haskell")
        self.assertEqual(len(results), 0)

    def test_search_regex(self) -> None:
        results = self.searcher.search(self.blocks, r"Python|Rust", regex=True)
        self.assertEqual(len(results), 3)

    def test_search_line_numbers(self) -> None:
        results = self.searcher.search(self.blocks, "Java")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].line, 2)

    def test_search_turn_range(self) -> None:
        results = self.searcher.search_turn_range(
            self.blocks, "Python", start_turn=2, end_turn=3
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].turn, 2)

    def test_rank_results(self) -> None:
        results = [
            SearchResult(turn=1, line=1, text="a", score=0.5),
            SearchResult(turn=2, line=1, text="b", score=1.0),
            SearchResult(turn=3, line=1, text="c", score=0.8),
        ]
        ranked = self.searcher.rank_results(results)
        self.assertEqual(ranked[0].score, 1.0)
        self.assertEqual(ranked[-1].score, 0.5)

    def test_count_matches(self) -> None:
        count = self.searcher.count_matches(self.blocks, "Python")
        self.assertEqual(count, 2)

    def test_summary_with_results(self) -> None:
        results = self.searcher.search(self.blocks, "Python")
        summary = self.searcher.summary(results)
        self.assertIn("2 matches", summary)
        self.assertIn("2 turns", summary)

    def test_summary_empty(self) -> None:
        summary = self.searcher.summary([])
        self.assertIn("No matches", summary)

    def test_context_included(self) -> None:
        results = self.searcher.search(self.blocks, "Java")
        self.assertTrue(results[0].context)


if __name__ == "__main__":
    unittest.main()
