"""
SQL Query Tool — execute SQL against local SQLite databases (and optionally
PostgreSQL/MySQL via a connection string).

Stdlib sqlite3 is always available. PostgreSQL/MySQL require optional deps
(psycopg2 / mysql-connector-python). Falls back gracefully if not installed.

Primary use-case: inspect and query project databases during development.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SqlResult:
    """Result of a SQL query."""
    query: str
    columns: list[str]
    rows: list[tuple[Any, ...]]
    rowcount: int          # affected rows for DML; -1 for SELECT
    elapsed_ms: float
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    def as_dicts(self) -> list[dict[str, Any]]:
        """Return rows as list of dicts keyed by column name."""
        return [dict(zip(self.columns, row)) for row in self.rows]

    def format_table(self, max_rows: int = 50) -> str:
        """Format result as an ASCII table."""
        if self.error:
            return f"Error: {self.error}"
        if not self.columns and not self.rows:
            return f"OK — {self.rowcount} row(s) affected ({self.elapsed_ms:.0f}ms)"

        display_rows = self.rows[:max_rows]
        col_widths = [len(str(c)) for c in self.columns]
        for row in display_rows:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val) if val is not None else "NULL"))

        sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
        header = "|" + "|".join(f" {str(c):<{w}} " for c, w in zip(self.columns, col_widths)) + "|"
        lines = [sep, header, sep]
        for row in display_rows:
            cells = []
            for val, w in zip(row, col_widths):
                s = str(val) if val is not None else "NULL"
                cells.append(f" {s:<{w}} ")
            lines.append("|" + "|".join(cells) + "|")
        lines.append(sep)
        lines.append(f"{len(self.rows)} row(s)  ({self.elapsed_ms:.0f}ms)")
        if len(self.rows) > max_rows:
            lines.append(f"(showing first {max_rows} of {len(self.rows)})")
        return "\n".join(lines)


@dataclass
class TableInfo:
    """Schema information for a database table."""
    name: str
    columns: list[dict[str, Any]]   # {"name", "type", "notnull", "pk", "default"}
    row_count: int = 0


# ---------------------------------------------------------------------------
# SqlTool
# ---------------------------------------------------------------------------

class SqlTool:
    """
    Execute SQL queries against a SQLite database file.

    Parameters
    ----------
    db_path : str | None
        Path to the SQLite database file. Use ":memory:" for in-memory DB.
    timeout : float
        SQLite busy timeout in seconds.
    """

    def __init__(
        self,
        db_path: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._db_path = db_path or ":memory:"
        self._timeout = timeout
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open the database connection."""
        if self._conn is not None:
            return
        self._conn = sqlite3.connect(self._db_path, timeout=self._timeout)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "SqlTool":
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, query: str, params: tuple | list | None = None) -> SqlResult:
        """
        Execute a SQL query and return a SqlResult.

        Parameters
        ----------
        query : str
            SQL statement to execute.
        params : tuple | list | None
            Positional parameters for parameterized queries (?).
        """
        self.connect()
        assert self._conn is not None
        start = time.monotonic()
        try:
            cur = self._conn.cursor()
            cur.execute(query, params or ())
            elapsed = (time.monotonic() - start) * 1000

            # DML (INSERT/UPDATE/DELETE) — commit and return rowcount
            q_upper = query.lstrip().upper()
            is_select = q_upper.startswith("SELECT") or q_upper.startswith("WITH")
            is_pragma = q_upper.startswith("PRAGMA")

            if is_select or is_pragma:
                rows_raw = cur.fetchall()
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows = [tuple(row) for row in rows_raw]
                return SqlResult(
                    query=query,
                    columns=columns,
                    rows=rows,
                    rowcount=len(rows),
                    elapsed_ms=elapsed,
                )
            else:
                self._conn.commit()
                return SqlResult(
                    query=query,
                    columns=[],
                    rows=[],
                    rowcount=cur.rowcount,
                    elapsed_ms=elapsed,
                )
        except sqlite3.Error as exc:
            elapsed = (time.monotonic() - start) * 1000
            return SqlResult(
                query=query,
                columns=[],
                rows=[],
                rowcount=-1,
                elapsed_ms=elapsed,
                error=str(exc),
            )

    def execute_many(self, query: str, params_list: list[tuple]) -> SqlResult:
        """Execute a parameterized query with multiple parameter sets."""
        self.connect()
        assert self._conn is not None
        start = time.monotonic()
        try:
            cur = self._conn.cursor()
            cur.executemany(query, params_list)
            self._conn.commit()
            elapsed = (time.monotonic() - start) * 1000
            return SqlResult(
                query=query,
                columns=[],
                rows=[],
                rowcount=cur.rowcount,
                elapsed_ms=elapsed,
            )
        except sqlite3.Error as exc:
            elapsed = (time.monotonic() - start) * 1000
            return SqlResult(
                query=query,
                columns=[],
                rows=[],
                rowcount=-1,
                elapsed_ms=elapsed,
                error=str(exc),
            )

    def execute_script(self, script: str) -> SqlResult:
        """Execute a multi-statement SQL script."""
        self.connect()
        assert self._conn is not None
        start = time.monotonic()
        try:
            self._conn.executescript(script)
            elapsed = (time.monotonic() - start) * 1000
            return SqlResult(
                query=script[:100] + ("..." if len(script) > 100 else ""),
                columns=[],
                rows=[],
                rowcount=-1,
                elapsed_ms=elapsed,
            )
        except sqlite3.Error as exc:
            elapsed = (time.monotonic() - start) * 1000
            return SqlResult(
                query=script[:100],
                columns=[],
                rows=[],
                rowcount=-1,
                elapsed_ms=elapsed,
                error=str(exc),
            )

    def list_tables(self) -> list[str]:
        """Return names of all user tables in the database."""
        result = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return [row[0] for row in result.rows]

    def table_info(self, table_name: str) -> TableInfo:
        """Return schema information for a table."""
        pragma = self.execute(f"PRAGMA table_info({table_name})")
        columns = []
        for row in pragma.rows:
            # cid, name, type, notnull, dflt_value, pk
            columns.append({
                "name": row[1],
                "type": row[2],
                "notnull": bool(row[3]),
                "default": row[4],
                "pk": bool(row[5]),
            })
        count_result = self.execute(f"SELECT COUNT(*) FROM {table_name}")  # noqa: S608
        row_count = count_result.rows[0][0] if count_result.rows else 0
        return TableInfo(name=table_name, columns=columns, row_count=row_count)

    def from_file(self, db_path: str) -> "SqlTool":
        """Return a new SqlTool pointed at a different database file."""
        return SqlTool(db_path=db_path, timeout=self._timeout)
