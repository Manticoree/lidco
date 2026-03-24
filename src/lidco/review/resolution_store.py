"""ResolutionStore — track which review comments have been resolved."""
from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path


class ResolutionStore:
    """SQLite-backed store of resolved review comment hashes."""

    def __init__(self, project_dir: Path | None = None) -> None:
        self._project_dir = project_dir or Path.cwd()
        self._db_path = self._project_dir / ".lidco" / "review_resolutions.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS resolutions (
                    hash TEXT PRIMARY KEY,
                    pr_number TEXT,
                    resolved_at REAL,
                    body TEXT
                )"""
            )

    @staticmethod
    def _hash(body: str, path: str = "", line: int = 0) -> str:
        data = f"{path}:{line}:{body}"
        return hashlib.md5(data.encode()).hexdigest()

    def mark_resolved(self, body: str, path: str = "", line: int = 0, pr_number: str = "") -> None:
        h = self._hash(body, path, line)
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO resolutions (hash, pr_number, resolved_at, body) VALUES (?,?,?,?)",
                (h, pr_number, time.time(), body),
            )

    def is_resolved(self, body: str, path: str = "", line: int = 0) -> bool:
        h = self._hash(body, path, line)
        with self._conn() as conn:
            row = conn.execute("SELECT 1 FROM resolutions WHERE hash=?", (h,)).fetchone()
        return row is not None

    def list_resolved(self, pr_number: str | None = None) -> list[dict]:
        with self._conn() as conn:
            if pr_number:
                rows = conn.execute(
                    "SELECT hash, pr_number, resolved_at, body FROM resolutions WHERE pr_number=?",
                    (pr_number,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT hash, pr_number, resolved_at, body FROM resolutions"
                ).fetchall()
        return [{"hash": r[0], "pr_number": r[1], "resolved_at": r[2], "body": r[3]} for r in rows]

    def unmark_resolved(self, body: str, path: str = "", line: int = 0) -> bool:
        h = self._hash(body, path, line)
        with self._conn() as conn:
            conn.execute("DELETE FROM resolutions WHERE hash=?", (h,))
        return True

    def clear(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM resolutions")
