"""QueryOptimizer2 — analyze SQL queries, suggest indexes, rewrite for performance."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnalysisResult:
    """Result of SQL query analysis."""

    sql: str
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    estimated_cost: str = "unknown"
    uses_index: bool = False


@dataclass
class IndexSuggestion:
    """A suggested index for a query."""

    table: str
    columns: list[str]
    reason: str


class QueryOptimizer2:
    """Analyze SQL queries for performance issues and suggest improvements."""

    def __init__(self) -> None:
        self._known_indexes: dict[str, list[list[str]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_index(self, table: str, columns: list[str]) -> None:
        """Register a known index so analysis can detect coverage."""
        existing = self._known_indexes.get(table, [])
        self._known_indexes = {
            **self._known_indexes,
            table: [*existing, list(columns)],
        }

    def analyze(self, sql: str) -> AnalysisResult:
        """Analyze a SQL query and return issues/suggestions."""
        normalized = self._normalize(sql)
        issues: list[str] = []
        suggestions: list[str] = []

        # SELECT *
        if re.search(r"\bSELECT\s+\*", normalized, re.IGNORECASE):
            issues.append("SELECT * detected — specify columns explicitly.")
            suggestions.append("Replace SELECT * with explicit column list.")

        # Missing WHERE on UPDATE/DELETE
        if re.search(r"\b(UPDATE|DELETE)\b", normalized, re.IGNORECASE):
            if not re.search(r"\bWHERE\b", normalized, re.IGNORECASE):
                issues.append("UPDATE/DELETE without WHERE clause — affects all rows.")
                suggestions.append("Add a WHERE clause to limit affected rows.")

        # Subquery in WHERE
        if re.search(r"\bWHERE\b.*\(\s*SELECT\b", normalized, re.IGNORECASE):
            issues.append("Correlated subquery detected — may be slow on large tables.")
            suggestions.append("Consider rewriting as a JOIN.")

        # LIKE with leading wildcard
        if re.search(r"LIKE\s+['\"]%", normalized, re.IGNORECASE):
            issues.append("LIKE with leading wildcard — prevents index usage.")
            suggestions.append("Avoid leading wildcards or use full-text search.")

        # ORDER BY without LIMIT
        if re.search(r"\bORDER\s+BY\b", normalized, re.IGNORECASE):
            if not re.search(r"\bLIMIT\b", normalized, re.IGNORECASE):
                suggestions.append("Consider adding LIMIT when using ORDER BY.")

        # Check index coverage
        tables = self._extract_tables(normalized)
        where_cols = self._extract_where_columns(normalized)
        uses_index = False
        for tbl in tables:
            known = self._known_indexes.get(tbl, [])
            for idx_cols in known:
                for wc in where_cols:
                    if wc in idx_cols:
                        uses_index = True

        cost = "low" if uses_index and not issues else ("high" if issues else "medium")

        return AnalysisResult(
            sql=sql,
            issues=issues,
            suggestions=suggestions,
            estimated_cost=cost,
            uses_index=uses_index,
        )

    def suggest_indexes(self, sql: str) -> list[IndexSuggestion]:
        """Suggest indexes that would help a query."""
        normalized = self._normalize(sql)
        suggestions: list[IndexSuggestion] = []

        tables = self._extract_tables(normalized)
        where_cols = self._extract_where_columns(normalized)
        order_cols = self._extract_order_columns(normalized)
        join_cols = self._extract_join_columns(normalized)

        for tbl in tables:
            known = self._known_indexes.get(tbl, [])

            # WHERE columns
            for col in where_cols:
                if not self._col_indexed(col, known):
                    suggestions.append(IndexSuggestion(
                        table=tbl,
                        columns=[col],
                        reason=f"Column '{col}' used in WHERE clause.",
                    ))

            # JOIN columns
            for col in join_cols:
                if not self._col_indexed(col, known):
                    suggestions.append(IndexSuggestion(
                        table=tbl,
                        columns=[col],
                        reason=f"Column '{col}' used in JOIN condition.",
                    ))

            # ORDER BY columns
            for col in order_cols:
                if not self._col_indexed(col, known):
                    suggestions.append(IndexSuggestion(
                        table=tbl,
                        columns=[col],
                        reason=f"Column '{col}' used in ORDER BY.",
                    ))

        return suggestions

    def rewrite(self, sql: str) -> str:
        """Attempt to rewrite a SQL query for better performance."""
        result = sql

        # Replace SELECT * with SELECT columns (placeholder)
        result = re.sub(
            r"\bSELECT\s+\*\s+FROM\b",
            "SELECT /* specify columns */ * FROM",
            result,
            flags=re.IGNORECASE,
        )

        # Add LIMIT to unbounded ORDER BY
        if re.search(r"\bORDER\s+BY\b", result, re.IGNORECASE):
            if not re.search(r"\bLIMIT\b", result, re.IGNORECASE):
                result = result.rstrip().rstrip(";") + " LIMIT 1000;"

        # Suggest JOIN for subquery
        if re.search(r"\bWHERE\b.*\bIN\s*\(\s*SELECT\b", result, re.IGNORECASE):
            result = result + "\n-- Consider rewriting subquery as JOIN"

        return result

    def explain(self, sql: str) -> dict[str, Any]:
        """Return a simulated EXPLAIN plan for a SQL query."""
        normalized = self._normalize(sql)
        tables = self._extract_tables(normalized)
        where_cols = self._extract_where_columns(normalized)

        scan_type = "full_scan"
        for tbl in tables:
            known = self._known_indexes.get(tbl, [])
            for idx_cols in known:
                for wc in where_cols:
                    if wc in idx_cols:
                        scan_type = "index_scan"

        has_join = bool(re.search(r"\bJOIN\b", normalized, re.IGNORECASE))
        has_sort = bool(re.search(r"\bORDER\s+BY\b", normalized, re.IGNORECASE))
        has_group = bool(re.search(r"\bGROUP\s+BY\b", normalized, re.IGNORECASE))

        return {
            "tables": tables,
            "scan_type": scan_type,
            "where_columns": where_cols,
            "has_join": has_join,
            "has_sort": has_sort,
            "has_group": has_group,
            "estimated_rows": "unknown",
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(sql: str) -> str:
        return " ".join(sql.split())

    @staticmethod
    def _extract_tables(sql: str) -> list[str]:
        tables: list[str] = []
        # FROM table
        for m in re.finditer(r"\bFROM\s+(\w+)", sql, re.IGNORECASE):
            tables.append(m.group(1))
        # JOIN table
        for m in re.finditer(r"\bJOIN\s+(\w+)", sql, re.IGNORECASE):
            tables.append(m.group(1))
        # UPDATE table
        for m in re.finditer(r"\bUPDATE\s+(\w+)", sql, re.IGNORECASE):
            tables.append(m.group(1))
        # DELETE FROM table
        for m in re.finditer(r"\bDELETE\s+FROM\s+(\w+)", sql, re.IGNORECASE):
            tables.append(m.group(1))
        return list(dict.fromkeys(tables))  # dedupe preserving order

    @staticmethod
    def _extract_where_columns(sql: str) -> list[str]:
        cols: list[str] = []
        # Simple pattern: column = value, column > value, etc.
        for m in re.finditer(r"\bWHERE\b(.+?)(?:\bORDER\b|\bGROUP\b|\bLIMIT\b|\bHAVING\b|$)", sql, re.IGNORECASE | re.DOTALL):
            clause = m.group(1)
            for cm in re.finditer(r"(\w+)\s*(?:=|!=|<>|>=?|<=?|LIKE\b|IN\b|IS\b)", clause, re.IGNORECASE):
                cols.append(cm.group(1))
        return list(dict.fromkeys(cols))

    @staticmethod
    def _extract_order_columns(sql: str) -> list[str]:
        cols: list[str] = []
        for m in re.finditer(r"\bORDER\s+BY\s+(.+?)(?:\bLIMIT\b|$)", sql, re.IGNORECASE | re.DOTALL):
            clause = m.group(1)
            for cm in re.finditer(r"(\w+)", clause):
                word = cm.group(1).upper()
                if word not in ("ASC", "DESC", "NULLS", "FIRST", "LAST"):
                    cols.append(cm.group(1))
        return list(dict.fromkeys(cols))

    @staticmethod
    def _extract_join_columns(sql: str) -> list[str]:
        cols: list[str] = []
        for m in re.finditer(r"\bON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)", sql, re.IGNORECASE):
            cols.append(m.group(2))
            cols.append(m.group(4))
        return list(dict.fromkeys(cols))

    @staticmethod
    def _col_indexed(col: str, indexes: list[list[str]]) -> bool:
        return any(col in idx for idx in indexes)
