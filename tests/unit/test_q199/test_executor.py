"""Tests for lidco.query.executor (Q199)."""
from __future__ import annotations

import unittest

from lidco.query.executor import QueryExecutor, QueryResult, SymbolRecord
from lidco.query.parser import OrderClause, ParsedQuery, WhereClause


def _rec(name: str, kind: str = "function", file: str = "a.py", line: int = 1) -> SymbolRecord:
    return SymbolRecord(name=name, kind=kind, file=file, line=line)


class TestQueryExecutor(unittest.TestCase):
    def setUp(self):
        self.records = [
            _rec("foo", "function", "a.py", 10),
            _rec("Bar", "class", "b.py", 20),
            _rec("baz", "function", "a.py", 30),
            _rec("Qux", "class", "c.py", 5),
        ]
        self.executor = QueryExecutor(self.records)

    def test_count(self):
        self.assertEqual(self.executor.count(), 4)

    def test_add_record(self):
        ex = QueryExecutor()
        ex.add_record(_rec("x"))
        self.assertEqual(ex.count(), 1)

    def test_add_records(self):
        ex = QueryExecutor()
        ex.add_records(self.records)
        self.assertEqual(ex.count(), 4)

    def test_clear(self):
        self.executor.clear()
        self.assertEqual(self.executor.count(), 0)

    def test_select_all(self):
        q = ParsedQuery(select_fields=("name", "kind"))
        result = self.executor.execute(q)
        self.assertEqual(result.total, 4)
        self.assertEqual(len(result.records), 4)

    def test_where_filter(self):
        q = ParsedQuery(
            select_fields=("name",),
            where_clauses=(WhereClause("kind", "=", "function"),),
        )
        result = self.executor.execute(q)
        self.assertEqual(result.total, 2)
        names = [r.name for r in result.records]
        self.assertIn("foo", names)
        self.assertIn("baz", names)

    def test_order_by_ascending(self):
        q = ParsedQuery(
            select_fields=("name",),
            order_by=(OrderClause("name", ascending=True),),
        )
        result = self.executor.execute(q)
        names = [r.name for r in result.records]
        self.assertEqual(names, sorted(names))

    def test_order_by_descending(self):
        q = ParsedQuery(
            select_fields=("name",),
            order_by=(OrderClause("line", ascending=False),),
        )
        result = self.executor.execute(q)
        lines = [r.line for r in result.records]
        self.assertEqual(lines, sorted(lines, reverse=True))

    def test_limit(self):
        q = ParsedQuery(select_fields=("name",), limit=2)
        result = self.executor.execute(q)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.total, 4)

    def test_combined_query(self):
        q = ParsedQuery(
            select_fields=("name",),
            where_clauses=(WhereClause("kind", "=", "function"),),
            order_by=(OrderClause("line", ascending=True),),
            limit=1,
        )
        result = self.executor.execute(q)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].name, "foo")
        self.assertEqual(result.total, 2)

    def test_empty_result(self):
        q = ParsedQuery(
            select_fields=("name",),
            where_clauses=(WhereClause("kind", "=", "nonexistent"),),
        )
        result = self.executor.execute(q)
        self.assertEqual(result.total, 0)
        self.assertEqual(result.records, [])

    def test_query_time(self):
        q = ParsedQuery(select_fields=("name",))
        result = self.executor.execute(q)
        self.assertGreaterEqual(result.query_time_ms, 0.0)


if __name__ == "__main__":
    unittest.main()
