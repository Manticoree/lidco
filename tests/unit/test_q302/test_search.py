"""Tests for lidco.githistory.search."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from lidco.githistory.search import HistorySearch, SearchCommit, SearchResult


class TestSearchCommit(unittest.TestCase):
    def test_fields(self):
        c = SearchCommit(hash="h1", message="msg", diff="diff", author="A", date=datetime(2026, 1, 1))
        self.assertEqual(c.hash, "h1")

    def test_immutable(self):
        c = SearchCommit(hash="h1", message="msg", diff="diff", author="A", date=datetime(2026, 1, 1))
        with self.assertRaises(AttributeError):
            c.hash = "new"  # type: ignore[misc]


class TestSearchResult(unittest.TestCase):
    def test_defaults(self):
        r = SearchResult(hash="h", author="A", date=datetime(2026, 1, 1), message="m")
        self.assertEqual(r.match_context, "")


class TestHistorySearch(unittest.TestCase):
    def setUp(self):
        self.hs = HistorySearch()
        base = datetime(2026, 1, 1)
        self.hs.add_commit("h1", "fix login bug", "+    if user.valid():", "Alice", base)
        self.hs.add_commit("h2", "add signup feature", "+    register(email)", "Bob", base + timedelta(days=1))
        self.hs.add_commit("h3", "refactor auth module", "-old_auth\n+new_auth", "Alice", base + timedelta(days=2))
        self.hs.add_commit("h4", "update README", "+docs only", "Charlie", base + timedelta(days=3))

    def test_count(self):
        self.assertEqual(self.hs.count, 4)

    def test_search_messages_found(self):
        results = self.hs.search_messages("login")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hash, "h1")

    def test_search_messages_case_insensitive(self):
        results = self.hs.search_messages("FIX")
        self.assertEqual(len(results), 1)

    def test_search_messages_no_match(self):
        results = self.hs.search_messages("zzz_no_match")
        self.assertEqual(results, [])

    def test_search_diffs_regex(self):
        results = self.hs.search_diffs(r"register\(")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hash, "h2")

    def test_search_diffs_invalid_regex(self):
        results = self.hs.search_diffs("[invalid")
        self.assertEqual(results, [])

    def test_search_diffs_match_context(self):
        results = self.hs.search_diffs(r"new_auth")
        self.assertEqual(len(results), 1)
        self.assertIn("new_auth", results[0].match_context)

    def test_by_author(self):
        results = self.hs.by_author("Alice")
        self.assertEqual(len(results), 2)

    def test_by_author_case_insensitive(self):
        results = self.hs.by_author("alice")
        self.assertEqual(len(results), 2)

    def test_by_author_no_match(self):
        results = self.hs.by_author("Nobody")
        self.assertEqual(results, [])

    def test_by_date_range(self):
        base = datetime(2026, 1, 1)
        results = self.hs.by_date_range(base, base + timedelta(days=1))
        self.assertEqual(len(results), 2)

    def test_by_date_range_empty(self):
        results = self.hs.by_date_range(datetime(2020, 1, 1), datetime(2020, 12, 31))
        self.assertEqual(results, [])

    def test_combined_message_and_author(self):
        results = self.hs.combined({"message": "auth", "author": "Alice"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hash, "h3")

    def test_combined_empty_filters(self):
        results = self.hs.combined({})
        self.assertEqual(results, [])

    def test_combined_no_overlap(self):
        results = self.hs.combined({"message": "login", "author": "Charlie"})
        self.assertEqual(results, [])

    def test_combined_with_dates(self):
        base = datetime(2026, 1, 1)
        results = self.hs.combined({
            "author": "Alice",
            "start_date": base,
            "end_date": base + timedelta(days=2),
        })
        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
