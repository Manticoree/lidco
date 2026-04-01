"""Structured query parser -- SQL-like syntax for code queries."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class QueryParseError(Exception):
    """Raised when a query cannot be parsed."""


@dataclass(frozen=True)
class QueryToken:
    """A single token from a parsed query."""

    type: str  # SELECT, WHERE, ORDER, LIMIT, FIELD, OP, VALUE, AND, OR, COMMA
    value: str


@dataclass(frozen=True)
class WhereClause:
    """A single WHERE condition."""

    field: str
    operator: str  # =, !=, >, <, >=, <=, LIKE, IN
    value: Any


@dataclass(frozen=True)
class OrderClause:
    """A single ORDER BY clause."""

    field: str
    ascending: bool = True


@dataclass(frozen=True)
class ParsedQuery:
    """Result of parsing a query string."""

    select_fields: tuple[str, ...]
    where_clauses: tuple[WhereClause, ...] = ()
    order_by: tuple[OrderClause, ...] = ()
    limit: int | None = None
    raw: str = ""


_KEYWORDS = {"SELECT", "WHERE", "ORDER", "BY", "LIMIT", "AND", "OR", "ASC", "DESC"}
_OPS = {"=", "!=", ">", "<", ">=", "<=", "LIKE", "IN"}


class QueryParser:
    """Parse SQL-like query strings into structured objects."""

    # ------------------------------------------------------------------
    # tokenize
    # ------------------------------------------------------------------

    def tokenize(self, query: str) -> list[QueryToken]:
        """Tokenize *query* into a flat list of ``QueryToken``s."""
        tokens: list[QueryToken] = []
        pos = 0
        text = query.strip()

        while pos < len(text):
            # skip whitespace
            if text[pos].isspace():
                pos += 1
                continue

            # comma
            if text[pos] == ",":
                tokens.append(QueryToken("COMMA", ","))
                pos += 1
                continue

            # quoted string value
            if text[pos] in ("'", '"'):
                quote = text[pos]
                end = text.index(quote, pos + 1)
                tokens.append(QueryToken("VALUE", text[pos + 1 : end]))
                pos = end + 1
                continue

            # parenthesised list for IN (...)
            if text[pos] == "(":
                end = text.index(")", pos + 1)
                inner = text[pos + 1 : end]
                tokens.append(QueryToken("VALUE", inner.strip()))
                pos = end + 1
                continue

            # two-char operators
            if text[pos : pos + 2] in ("!=", ">=", "<="):
                tokens.append(QueryToken("OP", text[pos : pos + 2]))
                pos += 2
                continue

            # single-char operators
            if text[pos] in ("=", ">", "<"):
                tokens.append(QueryToken("OP", text[pos]))
                pos += 1
                continue

            # word
            m = re.match(r"[A-Za-z_][A-Za-z0-9_.*]*", text[pos:])
            if m:
                word = m.group(0)
                upper = word.upper()
                if upper == "SELECT":
                    tokens.append(QueryToken("SELECT", word))
                elif upper == "WHERE":
                    tokens.append(QueryToken("WHERE", word))
                elif upper == "ORDER":
                    tokens.append(QueryToken("ORDER", word))
                elif upper == "LIMIT":
                    tokens.append(QueryToken("LIMIT", word))
                elif upper == "AND":
                    tokens.append(QueryToken("AND", word))
                elif upper == "OR":
                    tokens.append(QueryToken("OR", word))
                elif upper in ("BY", "ASC", "DESC"):
                    tokens.append(QueryToken("FIELD", word))
                elif upper in _OPS:
                    tokens.append(QueryToken("OP", upper))
                else:
                    tokens.append(QueryToken("FIELD", word))
                pos += len(word)
                continue

            # numeric literal
            m = re.match(r"\d+", text[pos:])
            if m:
                tokens.append(QueryToken("VALUE", m.group(0)))
                pos += len(m.group(0))
                continue

            raise QueryParseError(f"Unexpected character at position {pos}: {text[pos]!r}")

        return tokens

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------

    def parse(self, query: str) -> ParsedQuery:
        """Parse a SQL-like *query* string into a ``ParsedQuery``."""
        tokens = self.tokenize(query)
        if not tokens:
            raise QueryParseError("Empty query")

        idx = 0

        # --- SELECT ---
        if tokens[idx].type != "SELECT":
            raise QueryParseError("Query must start with SELECT")
        idx += 1

        select_fields: list[str] = []
        while idx < len(tokens) and tokens[idx].type == "FIELD":
            select_fields.append(tokens[idx].value)
            idx += 1
            if idx < len(tokens) and tokens[idx].type == "COMMA":
                idx += 1
        if not select_fields:
            raise QueryParseError("SELECT requires at least one field")

        # --- WHERE ---
        where_clauses: list[WhereClause] = []
        if idx < len(tokens) and tokens[idx].type == "WHERE":
            idx += 1
            while idx < len(tokens):
                if tokens[idx].type in ("ORDER", "LIMIT"):
                    break
                if tokens[idx].type in ("AND", "OR"):
                    idx += 1
                    continue
                if tokens[idx].type != "FIELD":
                    raise QueryParseError(f"Expected field in WHERE clause, got {tokens[idx]}")
                fld = tokens[idx].value
                idx += 1
                if idx >= len(tokens) or tokens[idx].type != "OP":
                    raise QueryParseError(f"Expected operator after field '{fld}'")
                op = tokens[idx].value
                idx += 1
                if idx >= len(tokens):
                    raise QueryParseError(f"Expected value after operator '{op}'")
                val: Any = tokens[idx].value
                # try numeric conversion
                if tokens[idx].type == "VALUE":
                    try:
                        val = int(val)
                    except (ValueError, TypeError):
                        pass
                elif tokens[idx].type == "FIELD":
                    pass  # bare word value
                idx += 1
                where_clauses.append(WhereClause(field=fld, operator=op, value=val))

        # --- ORDER BY ---
        order_by: list[OrderClause] = []
        if idx < len(tokens) and tokens[idx].type == "ORDER":
            idx += 1
            # skip BY
            if idx < len(tokens) and tokens[idx].type == "FIELD" and tokens[idx].value.upper() == "BY":
                idx += 1
            while idx < len(tokens) and tokens[idx].type not in ("LIMIT",):
                if tokens[idx].type == "COMMA":
                    idx += 1
                    continue
                if tokens[idx].type != "FIELD":
                    break
                fld = tokens[idx].value
                idx += 1
                ascending = True
                if idx < len(tokens) and tokens[idx].type == "FIELD" and tokens[idx].value.upper() in ("ASC", "DESC"):
                    ascending = tokens[idx].value.upper() == "ASC"
                    idx += 1
                order_by.append(OrderClause(field=fld, ascending=ascending))

        # --- LIMIT ---
        limit: int | None = None
        if idx < len(tokens) and tokens[idx].type == "LIMIT":
            idx += 1
            if idx >= len(tokens):
                raise QueryParseError("LIMIT requires a number")
            try:
                limit = int(tokens[idx].value)
            except (ValueError, TypeError) as exc:
                raise QueryParseError(f"Invalid LIMIT value: {tokens[idx].value}") from exc
            idx += 1

        return ParsedQuery(
            select_fields=tuple(select_fields),
            where_clauses=tuple(where_clauses),
            order_by=tuple(order_by),
            limit=limit,
            raw=query,
        )

    # ------------------------------------------------------------------
    # validate
    # ------------------------------------------------------------------

    def validate(self, query: str) -> list[str]:
        """Return a list of error messages (empty if valid)."""
        errors: list[str] = []
        try:
            self.parse(query)
        except QueryParseError as exc:
            errors.append(str(exc))
        return errors
