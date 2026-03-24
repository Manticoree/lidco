"""AIContributionTracker — track AI vs human line contributions per file."""
from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ContributionRecord:
    file: str
    lines_added: int
    lines_removed: int
    author: str       # "ai" | "human"
    session_id: str
    timestamp: float


@dataclass
class ModuleMetrics:
    file: str
    ai_lines: int
    human_lines: int
    ai_ratio: float


class AIContributionTracker:
    """SQLite-backed tracker for AI vs human code contribution metrics."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            db_path = Path(".lidco") / "ai_contribution.db"
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS contributions (
                    id TEXT PRIMARY KEY,
                    file TEXT NOT NULL,
                    lines_added INTEGER NOT NULL DEFAULT 0,
                    lines_removed INTEGER NOT NULL DEFAULT 0,
                    author TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
                """
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        file: str,
        lines_added: int,
        lines_removed: int,
        author: str,
        session_id: str,
    ) -> ContributionRecord:
        """Insert a contribution record and return it."""
        rec = ContributionRecord(
            file=file,
            lines_added=lines_added,
            lines_removed=lines_removed,
            author=author,
            session_id=session_id,
            timestamp=time.time(),
        )
        row_id = str(uuid.uuid4())[:8]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO contributions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    row_id,
                    rec.file,
                    rec.lines_added,
                    rec.lines_removed,
                    rec.author,
                    rec.session_id,
                    rec.timestamp,
                ),
            )
        return rec

    def module_metrics(self, file: str) -> ModuleMetrics:
        """Compute AI vs human line totals for a specific file."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT author, SUM(lines_added) as total FROM contributions WHERE file = ? GROUP BY author",
                (file,),
            ).fetchall()

        ai_lines = 0
        human_lines = 0
        for row in rows:
            if row["author"] == "ai":
                ai_lines = row["total"] or 0
            else:
                human_lines = row["total"] or 0

        total = ai_lines + human_lines
        ai_ratio = ai_lines / total if total > 0 else 0.0

        return ModuleMetrics(
            file=file,
            ai_lines=ai_lines,
            human_lines=human_lines,
            ai_ratio=ai_ratio,
        )

    def session_summary(self, session_id: str) -> dict:
        """Return aggregate stats for a session."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT author, SUM(lines_added) as total FROM contributions WHERE session_id = ? GROUP BY author",
                (session_id,),
            ).fetchall()

        ai_lines = 0
        human_lines = 0
        for row in rows:
            if row["author"] == "ai":
                ai_lines = row["total"] or 0
            else:
                human_lines = row["total"] or 0

        total = ai_lines + human_lines
        ai_ratio = ai_lines / total if total > 0 else 0.0

        return {
            "ai_lines_added": ai_lines,
            "human_lines_added": human_lines,
            "ai_ratio": ai_ratio,
        }

    def all_modules(self) -> list[ModuleMetrics]:
        """Return ModuleMetrics for all tracked files, sorted by ai_ratio desc."""
        with self._connect() as conn:
            files = [
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT file FROM contributions"
                ).fetchall()
            ]

        metrics = [self.module_metrics(f) for f in files]
        metrics.sort(key=lambda m: m.ai_ratio, reverse=True)
        return metrics

    def dashboard_data(self) -> dict:
        """Return aggregate dashboard statistics."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT author, SUM(lines_added) as total FROM contributions GROUP BY author"
            ).fetchall()

        total_ai = 0
        total_human = 0
        for row in rows:
            if row["author"] == "ai":
                total_ai = row["total"] or 0
            else:
                total_human = row["total"] or 0

        grand_total = total_ai + total_human
        ai_ratio = total_ai / grand_total if grand_total > 0 else 0.0

        # Top 5 AI modules
        all_mods = self.all_modules()
        top_ai = [m.file for m in all_mods[:5]]

        return {
            "total_ai_lines": total_ai,
            "total_human_lines": total_human,
            "ai_ratio": ai_ratio,
            "top_ai_modules": top_ai,
        }
