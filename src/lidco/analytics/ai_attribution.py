"""AIAttributionStore — track which lines were written by AI vs human."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LineAttribution:
    file: str
    line: int
    author: str  # "ai" | "human"
    session_id: str
    timestamp: float
    model: str = ""


class AIAttributionStore:
    """SQLite-backed store for per-line AI vs human attribution."""

    _DEFAULT_DB = Path(".lidco/ai_attribution.db")

    _CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS attributions (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        file       TEXT NOT NULL,
        line       INTEGER NOT NULL,
        author     TEXT NOT NULL,
        session_id TEXT NOT NULL,
        timestamp  REAL NOT NULL,
        model      TEXT NOT NULL DEFAULT '',
        UNIQUE(file, line)
    )
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else self._DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(self._CREATE_SQL)
            conn.commit()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record_edit(
        self,
        file: str,
        start_line: int,
        end_line: int,
        author: str,
        session_id: str,
        model: str = "",
    ) -> int:
        """Insert one row per line in [start_line, end_line] inclusive.

        Uses INSERT OR REPLACE so the same file+line is overwritten.
        Returns count inserted/replaced.
        """
        ts = time.time()
        rows = [
            (file, line, author, session_id, ts, model)
            for line in range(start_line, end_line + 1)
        ]
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO attributions "
                "(file, line, author, session_id, timestamp, model) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()
        return len(rows)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_file_attribution(self, file: str) -> list[LineAttribution]:
        """Return all attributions for file, sorted by line ASC."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT file, line, author, session_id, timestamp, model "
                "FROM attributions WHERE file=? ORDER BY line ASC",
                (file,),
            ).fetchall()
        return [
            LineAttribution(
                file=row["file"],
                line=row["line"],
                author=row["author"],
                session_id=row["session_id"],
                timestamp=row["timestamp"],
                model=row["model"],
            )
            for row in rows
        ]

    def ai_ratio(self, file: str) -> float:
        """Return ratio of AI lines to total lines (0.0 if empty)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN author='ai' THEN 1 ELSE 0 END) as ai_count "
                "FROM attributions WHERE file=?",
                (file,),
            ).fetchone()
        total = row["total"] or 0
        if total == 0:
            return 0.0
        ai_count = row["ai_count"] or 0
        return ai_count / total

    def session_attribution(self, session_id: str) -> dict:
        """Return {ai_lines, human_lines} for the given session."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT author, COUNT(*) as cnt "
                "FROM attributions WHERE session_id=? "
                "GROUP BY author",
                (session_id,),
            ).fetchall()
        result = {"ai_lines": 0, "human_lines": 0}
        for row in rows:
            if row["author"] == "ai":
                result["ai_lines"] = row["cnt"]
            elif row["author"] == "human":
                result["human_lines"] = row["cnt"]
        return result

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def reconcile_with_diff(
        self,
        file: str,
        old_line_count: int,
        new_line_count: int,
        hunks: list[tuple],
    ) -> None:
        """Adjust line numbers after a diff is applied.

        hunks: [(old_start, old_count, new_start, new_count), ...]

        For each hunk:
        1. DELETE rows in [old_start, old_start + old_count - 1]
        2. Shift rows after the hunk by (new_count - old_count)
        """
        with self._connect() as conn:
            offset = 0
            for old_start, old_count, new_start, new_count in hunks:
                adjusted_old_start = old_start + offset

                # Delete lines that were replaced/removed
                old_end = adjusted_old_start + old_count - 1
                conn.execute(
                    "DELETE FROM attributions WHERE file=? AND line BETWEEN ? AND ?",
                    (file, adjusted_old_start, old_end),
                )

                # Shift lines after the hunk
                delta = new_count - old_count
                if delta != 0:
                    conn.execute(
                        "UPDATE attributions SET line = line + ? "
                        "WHERE file=? AND line > ?",
                        (delta, file, old_end),
                    )

                offset += delta

            conn.commit()

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear_file(self, file: str) -> int:
        """Delete all attributions for file; return count deleted."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM attributions WHERE file=?",
                (file,),
            )
            conn.commit()
            return cur.rowcount
