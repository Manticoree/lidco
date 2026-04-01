"""Tests for lidco.query.parser (Q199)."""
from __future__ import annotations

import unittest

from lidco.query.parser import (
    OrderClause,
    ParsedQuery,
    QueryParseError,
    QueryParser,
    QueryToken,
    WhereClause,
)


class TestTokenize(unittest.TestCase):
    def setUp(self):
        self.parser = QueryParser()

    def test_basic_select(self):
        tokens = self.parser.tokenize("SELECT name")
        self.assertEqual(tokens[0], QueryToken("SELECT", "SELECT"))
        self.assertEqual(tokens[1], QueryToken("FIELD", "name"))

    def test_operators(self):
        tokens = self.parser.tokenize("SELECT x WHERE y >= 10")
        ops = [t for t in tokens if t.type == "OP"]
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].value, ">=")


class TestParse(unittest.TestCase):
    def setUp(self):
        self.parser = QueryParser()

    def test_simple_select(self):
        q = self.parser.parse("SELECT name, kind")
        self.assertEqual(q.select_fields, ("name", "kind"))
        self.assertEqual(q.where_clauses, ())
        self.assertEqual(q.limit, None)

    def test_where_equals(self):
        q = self.parser.parse("SELECT name WHERE kind = 'function'")
        self.assertEqual(len(q.where_clauses), 1)
        self.assertEqual(q.where_clauses[0].field, "kind")
        self.assertEqual(q.where_clauses[0].operator, "=")
        self.assertEqual(q.where_clauses[0].value, "function")

    def test_where_not_equals(self):
        q = self.parser.parse("SELECT name WHERE kind != 'class'")
        self.assertEqual(q.where_clauses[0].operator, "!=")

    def test_where_greater_than(self):
        q = self.parser.parse("SELECT name WHERE line > 100")
        wc = q.where_clauses[0]
        self.assertEqual(wc.operator, ">")
        self.assertEqual(wc.value, 100)

    def test_where_like(self):
        q = self.parser.parse("SELECT name WHERE name LIKE 'test%'")
        self.assertEqual(q.where_clauses[0].operator, "LIKE")

    def test_order_by(self):
        q = self.parser.parse("SELECT name ORDER BY name")
        self.assertEqual(len(q.order_by), 1)
        self.assertEqual(q.order_by[0].field, "name")
        self.assertTrue(q.order_by[0].ascending)

    def test_order_by_desc(self):
        q = self.parser.parse("SELECT name ORDER BY line DESC")
        self.assertFalse(q.order_by[0].ascending)

    def test_limit(self):
        q = self.parser.parse("SELECT name LIMIT 5")
        self.assertEqual(q.limit, 5)

    def test_combined_query(self):
        q = self.parser.parse(
            "SELECT name, kind WHERE kind = 'function' ORDER BY name LIMIT 10"
        )
        self.assertEqual(q.select_fields, ("name", "kind"))
        self.assertEqual(len(q.where_clauses), 1)
        self.assertEqual(len(q.order_by), 1)
        self.assertEqual(q.limit, 10)

    def test_empty_query_raises(self):
        with self.assertRaises(QueryParseError):
            self.parser.parse("")


class TestValidate(unittest.TestCase):
    def setUp(self):
        self.parser = QueryParser()

    def test_valid_query(self):
        errors = self.parser.validate("SELECT name WHERE kind = 'function'")
        self.assertEqual(errors, [])

    def test_invalid_query(self):
        errors = self.parser.validate("INVALID stuff")
        self.assertTrue(len(errors) > 0)


if __name__ == "__main__":
    unittest.main()
