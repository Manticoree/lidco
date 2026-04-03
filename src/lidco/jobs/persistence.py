"""JobPersistenceStore — SQLite-backed job store (Q225)."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class JobRecord:
    """Persisted job record."""

    id: str
    name: str
    status: str  # pending / running / completed / failed / cancelled
    payload: str  # JSON string
    result: str | None
    created_at: float
    updated_at: float
    error: str | None = None


_VALID_STATUSES = {"pending", "running", "completed", "failed", "cancelled"}

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    result TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    error TEXT
)
"""


class JobPersistenceStore:
    """SQLite-backed persistence for job records."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(self, job: JobRecord) -> JobRecord:
        """Insert or update a job record."""
        now = time.time()
        updated = JobRecord(
            id=job.id,
            name=job.name,
            status=job.status,
            payload=job.payload,
            result=job.result,
            created_at=job.created_at,
            updated_at=now,
            error=job.error,
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO jobs (id, name, status, payload, result, created_at, updated_at, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (updated.id, updated.name, updated.status, updated.payload,
             updated.result, updated.created_at, updated.updated_at, updated.error),
        )
        self._conn.commit()
        return updated

    def get(self, job_id: str) -> JobRecord | None:
        """Fetch a single job by ID."""
        row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def query(
        self,
        status: str | None = None,
        name: str | None = None,
        limit: int = 100,
    ) -> list[JobRecord]:
        """Query jobs with optional filters."""
        clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if name is not None:
            clauses.append("name = ?")
            params.append(name)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM jobs{where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def update_status(
        self,
        job_id: str,
        status: str,
        result: str | None = None,
        error: str | None = None,
    ) -> JobRecord | None:
        """Update a job's status (and optionally result/error)."""
        existing = self.get(job_id)
        if existing is None:
            return None
        now = time.time()
        self._conn.execute(
            "UPDATE jobs SET status = ?, result = ?, error = ?, updated_at = ? WHERE id = ?",
            (status, result, error, now, job_id),
        )
        self._conn.commit()
        return JobRecord(
            id=existing.id,
            name=existing.name,
            status=status,
            payload=existing.payload,
            result=result,
            created_at=existing.created_at,
            updated_at=now,
            error=error,
        )

    def delete(self, job_id: str) -> bool:
        """Delete a job. Returns True if a row was removed."""
        cur = self._conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def cleanup(self, older_than: float) -> int:
        """Delete completed/failed jobs older than *older_than* timestamp."""
        cur = self._conn.execute(
            "DELETE FROM jobs WHERE status IN ('completed', 'failed') AND updated_at < ?",
            (older_than,),
        )
        self._conn.commit()
        return cur.rowcount

    def count(self, status: str | None = None) -> int:
        """Count jobs, optionally filtered by status."""
        if status is not None:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = ?", (status,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM jobs").fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            id=row["id"],
            name=row["name"],
            status=row["status"],
            payload=row["payload"],
            result=row["result"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error=row["error"],
        )
