"""Execute parsed queries against in-memory symbol data."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from lidco.query.parser import ParsedQuery, WhereClause


@dataclass(frozen=True)
class SymbolRecord:
    """A single symbol record."""

    name: str
    kind: str
    file: str
    line: int = 0
    module: str = ""
    docstring: str = ""


@dataclass
class QueryResult:
    """Result of executing a query."""

    records: list[SymbolRecord] = field(default_factory=list)
    total: int = 0
    query_time_ms: float = 0.0


def _get_field(record: SymbolRecord, field_name: str) -> Any:
    """Retrieve a field value from a record by name."""
    return getattr(record, field_name, "")


def _match_clause(record: SymbolRecord, clause: WhereClause) -> bool:
    """Return True if *record* satisfies *clause*."""
    val = _get_field(record, clause.field)
    target = clause.value
    op = clause.operator.upper()

    if op == "=":
        return str(val) == str(target)
    if op == "!=":
        return str(val) != str(target)
    if op == ">":
        return float(val) > float(target)
    if op == "<":
        return float(val) < float(target)
    if op == ">=":
        return float(val) >= float(target)
    if op == "<=":
        return float(val) <= float(target)
    if op == "LIKE":
        pattern = str(target).replace("%", ".*").replace("_", ".")
        return bool(re.fullmatch(pattern, str(val), re.IGNORECASE))
    if op == "IN":
        items = [i.strip().strip("'\"") for i in str(target).split(",")]
        return str(val) in items
    return False


class QueryExecutor:
    """Execute queries against a collection of ``SymbolRecord`` objects."""

    def __init__(self, records: list[SymbolRecord] | None = None) -> None:
        self._records: list[SymbolRecord] = list(records) if records else []

    # ------------------------------------------------------------------
    # record management
    # ------------------------------------------------------------------

    def add_record(self, record: SymbolRecord) -> None:
        self._records.append(record)

    def add_records(self, records: list[SymbolRecord]) -> None:
        self._records.extend(records)

    def count(self) -> int:
        return len(self._records)

    def clear(self) -> None:
        self._records.clear()

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    def execute(self, query: ParsedQuery) -> QueryResult:
        """Filter, sort, and limit records according to *query*."""
        t0 = time.monotonic()

        # filter
        results = self._records
        for clause in query.where_clauses:
            results = [r for r in results if _match_clause(r, clause)]

        # sort
        for order in reversed(query.order_by):
            results = sorted(
                results,
                key=lambda r, f=order.field: _get_field(r, f),
                reverse=not order.ascending,
            )

        total = len(results)

        # limit
        if query.limit is not None:
            results = results[: query.limit]

        elapsed = (time.monotonic() - t0) * 1000
        return QueryResult(records=results, total=total, query_time_ms=elapsed)
