"""Tests for Q150 LogSearcher."""
from __future__ import annotations

import unittest

from lidco.logging.structured_logger import LogRecord
from lidco.logging.log_searcher import LogSearcher, SearchQuery, SearchResult


def _rec(level="info", msg="test", name="app", ts=1.0, ctx=None, cid=None) -> LogRecord:
    return LogRecord(level=level, message=msg, timestamp=ts, logger_name=name,
                     context=ctx or {}, correlation_id=cid)


class TestSearchQuery(unittest.TestCase):
    def test_defaults(self):
        q = SearchQuery()
        self.assertIsNone(q.text)
        self.assertIsNone(q.level)
        self.assertEqual(q.limit, 100)


class TestSearchResult(unittest.TestCase):
    def test_fields(self):
        q = SearchQuery()
        r = SearchResult(records=[], total_matched=0, query=q)
        self.assertEqual(r.total_matched, 0)


class TestLogSearcher(unittest.TestCase):
    def setUp(self):
        self.searcher = LogSearcher()
        self.records = [
            _rec(level="debug", msg="startup", name="core", ts=100),
            _rec(level="info", msg="request received", name="http", ts=200, ctx={"path": "/api"}),
            _rec(level="warning", msg="slow query", name="db", ts=300),
            _rec(level="error", msg="connection failed", name="db", ts=400),
            _rec(level="info", msg="request received", name="http", ts=500, ctx={"path": "/home"}),
            _rec(level="critical", msg="disk full", name="core", ts=600),
        ]

    def test_search_all(self):
        result = self.searcher.search(self.records, SearchQuery())
        self.assertEqual(result.total_matched, 6)

    def test_search_by_level(self):
        result = self.searcher.search(self.records, SearchQuery(level="info"))
        self.assertEqual(result.total_matched, 2)

    def test_search_by_text(self):
        result = self.searcher.search(self.records, SearchQuery(text="request"))
        self.assertEqual(result.total_matched, 2)

    def test_search_text_case_insensitive(self):
        result = self.searcher.search(self.records, SearchQuery(text="REQUEST"))
        self.assertEqual(result.total_matched, 2)

    def test_search_by_logger_name(self):
        result = self.searcher.search(self.records, SearchQuery(logger_name="db"))
        self.assertEqual(result.total_matched, 2)

    def test_search_since(self):
        result = self.searcher.search(self.records, SearchQuery(since=300))
        self.assertEqual(result.total_matched, 4)

    def test_search_until(self):
        result = self.searcher.search(self.records, SearchQuery(until=200))
        self.assertEqual(result.total_matched, 2)

    def test_search_since_and_until(self):
        result = self.searcher.search(self.records, SearchQuery(since=200, until=400))
        self.assertEqual(result.total_matched, 3)

    def test_search_context_key(self):
        result = self.searcher.search(self.records, SearchQuery(context_key="path"))
        self.assertEqual(result.total_matched, 2)

    def test_search_context_key_and_value(self):
        result = self.searcher.search(self.records, SearchQuery(context_key="path", context_value="/api"))
        self.assertEqual(result.total_matched, 1)

    def test_search_limit(self):
        result = self.searcher.search(self.records, SearchQuery(limit=2))
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.total_matched, 6)

    def test_search_no_match(self):
        result = self.searcher.search(self.records, SearchQuery(text="xyz"))
        self.assertEqual(result.total_matched, 0)

    def test_search_empty_records(self):
        result = self.searcher.search([], SearchQuery())
        self.assertEqual(result.total_matched, 0)

    def test_search_combined_filters(self):
        result = self.searcher.search(self.records, SearchQuery(level="info", logger_name="http"))
        self.assertEqual(result.total_matched, 2)

    def test_count_by_level(self):
        counts = self.searcher.count_by_level(self.records)
        self.assertEqual(counts["debug"], 1)
        self.assertEqual(counts["info"], 2)
        self.assertEqual(counts["warning"], 1)
        self.assertEqual(counts["error"], 1)
        self.assertEqual(counts["critical"], 1)

    def test_count_by_level_empty(self):
        self.assertEqual(self.searcher.count_by_level([]), {})

    def test_timeline(self):
        tl = self.searcher.timeline(self.records, bucket_seconds=200)
        self.assertGreater(len(tl), 0)
        total = sum(count for _, count in tl)
        self.assertEqual(total, 6)

    def test_timeline_empty(self):
        self.assertEqual(self.searcher.timeline([]), [])

    def test_timeline_sorted(self):
        tl = self.searcher.timeline(self.records, bucket_seconds=100)
        timestamps = [t for t, _ in tl]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_top_loggers(self):
        top = self.searcher.top_loggers(self.records)
        names = [name for name, _ in top]
        self.assertIn("http", names)
        self.assertIn("db", names)
        # http and db each have 2 records
        self.assertEqual(top[0][1], 2)

    def test_top_loggers_n(self):
        top = self.searcher.top_loggers(self.records, n=1)
        self.assertEqual(len(top), 1)

    def test_top_loggers_empty(self):
        self.assertEqual(self.searcher.top_loggers([]), [])


if __name__ == "__main__":
    unittest.main()
