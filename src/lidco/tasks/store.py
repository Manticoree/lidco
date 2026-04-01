"""Persistent task storage with SQLite."""
from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class StoredTask:
    id: str
    name: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = 0.0
    updated_at: float = 0.0
    output: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskStoreError(Exception):
    """Raised on task store errors."""


class TaskStore:
    """SQLite-backed persistent task storage."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                output TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}'
            )"""
        )
        self._conn.commit()

    def _row_to_task(self, row: sqlite3.Row) -> StoredTask:
        import json

        md = row["metadata"]
        meta = json.loads(md) if md else {}
        return StoredTask(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            status=TaskStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            output=row["output"],
            error=row["error"],
            metadata=meta,
        )

    def create(
        self,
        name: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> StoredTask:
        import json

        task_id = uuid.uuid4().hex[:8]
        now = time.time()
        meta = metadata or {}
        self._conn.execute(
            "INSERT INTO tasks (id, name, description, status, created_at, updated_at, output, error, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, name, description, TaskStatus.PENDING.value, now, now, "", "", json.dumps(meta)),
        )
        self._conn.commit()
        return StoredTask(
            id=task_id,
            name=name,
            description=description,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            output="",
            error="",
            metadata=meta,
        )

    def get(self, task_id: str) -> StoredTask | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_task(row)

    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        output: str = "",
        error: str = "",
    ) -> StoredTask:
        now = time.time()
        cur = self._conn.execute(
            "UPDATE tasks SET status = ?, output = ?, error = ?, updated_at = ? WHERE id = ?",
            (status.value, output, error, now, task_id),
        )
        self._conn.commit()
        if cur.rowcount == 0:
            raise TaskStoreError(f"Task '{task_id}' not found")
        task = self.get(task_id)
        assert task is not None
        return task

    def list_tasks(self, status: TaskStatus | None = None) -> list[StoredTask]:
        if status is not None:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at", (status.value,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM tasks ORDER BY created_at").fetchall()
        return [self._row_to_task(r) for r in rows]

    def delete(self, task_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def count(self, status: TaskStatus | None = None) -> int:
        if status is not None:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = ?", (status.value,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
        return row[0]

    def clear(self) -> int:
        cur = self._conn.execute("DELETE FROM tasks")
        self._conn.commit()
        return cur.rowcount
