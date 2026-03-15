"""Async task queue — Task 328.

Persistent async task queue backed by SQLite. Tasks can be submitted,
queried, cancelled, and their results retrieved.

Usage::

    queue = TaskQueue(db_path=".lidco/tasks.db")
    task_id = queue.submit("Refactor auth module", agent="refactor")
    status = queue.get(task_id)
    print(status.state)   # queued | running | done | failed | cancelled
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_DEFAULT_DB = Path(".lidco") / "tasks.db"


class TaskState:
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """A single queued task."""

    task_id: str
    prompt: str
    state: str = TaskState.QUEUED
    agent: str = ""
    model: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    finished_at: float = 0.0
    result: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.state in (TaskState.DONE, TaskState.FAILED, TaskState.CANCELLED)

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.finished_at:
            return self.finished_at - self.started_at
        return 0.0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "prompt": self.prompt,
            "state": self.state,
            "agent": self.agent,
            "model": self.model,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class TaskNotFoundError(Exception):
    pass


class TaskQueue:
    """Persistent async task queue backed by SQLite.

    Args:
        db_path: Path to the SQLite database file.
    """

    _CREATE_SQL = """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id      TEXT PRIMARY KEY,
            prompt       TEXT NOT NULL,
            state        TEXT NOT NULL DEFAULT 'queued',
            agent        TEXT NOT NULL DEFAULT '',
            model        TEXT NOT NULL DEFAULT '',
            created_at   REAL NOT NULL,
            started_at   REAL NOT NULL DEFAULT 0.0,
            finished_at  REAL NOT NULL DEFAULT 0.0,
            result       TEXT NOT NULL DEFAULT '',
            error        TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_state ON tasks(state);
        CREATE INDEX IF NOT EXISTS idx_created ON tasks(created_at);
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._path = Path(db_path) if db_path else _DEFAULT_DB
        self._conn: sqlite3.Connection | None = None

    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
            self._conn.executescript(self._CREATE_SQL)
            self._conn.commit()
        return self._conn

    # ------------------------------------------------------------------
    # Submit / update
    # ------------------------------------------------------------------

    def submit(
        self,
        prompt: str,
        agent: str = "",
        model: str = "",
        metadata: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> str:
        """Submit a new task. Returns task_id."""
        tid = task_id or str(uuid.uuid4())
        now = time.time()
        self._db().execute(
            """
            INSERT INTO tasks
                (task_id, prompt, state, agent, model, created_at, metadata_json)
            VALUES (?, ?, 'queued', ?, ?, ?, ?)
            """,
            (tid, prompt, agent, model, now, json.dumps(metadata or {})),
        )
        self._db().commit()
        return tid

    def start(self, task_id: str) -> None:
        """Mark a task as running."""
        conn = self._db()
        if not self._exists(task_id):
            raise TaskNotFoundError(task_id)
        conn.execute(
            "UPDATE tasks SET state='running', started_at=? WHERE task_id=?",
            (time.time(), task_id),
        )
        conn.commit()

    def complete(self, task_id: str, result: str = "") -> None:
        """Mark a task as done with a result."""
        conn = self._db()
        if not self._exists(task_id):
            raise TaskNotFoundError(task_id)
        conn.execute(
            "UPDATE tasks SET state='done', result=?, finished_at=? WHERE task_id=?",
            (result, time.time(), task_id),
        )
        conn.commit()

    def fail(self, task_id: str, error: str = "") -> None:
        """Mark a task as failed."""
        conn = self._db()
        if not self._exists(task_id):
            raise TaskNotFoundError(task_id)
        conn.execute(
            "UPDATE tasks SET state='failed', error=?, finished_at=? WHERE task_id=?",
            (error, time.time(), task_id),
        )
        conn.commit()

    def cancel(self, task_id: str) -> bool:
        """Cancel a task. Returns True if it was cancellable."""
        conn = self._db()
        task = self.get(task_id)
        if task is None:
            return False
        if task.state not in (TaskState.QUEUED, TaskState.RUNNING):
            return False
        conn.execute(
            "UPDATE tasks SET state='cancelled', finished_at=? WHERE task_id=?",
            (time.time(), task_id),
        )
        conn.commit()
        return True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, task_id: str) -> Task | None:
        row = self._db().execute(
            "SELECT * FROM tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        return self._row_to_task(row) if row else None

    def list_tasks(
        self,
        state: str | None = None,
        limit: int = 50,
    ) -> list[Task]:
        if state:
            rows = self._db().execute(
                "SELECT * FROM tasks WHERE state=? ORDER BY created_at DESC LIMIT ?",
                (state, limit),
            ).fetchall()
        else:
            rows = self._db().execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def count(self, state: str | None = None) -> int:
        if state:
            row = self._db().execute(
                "SELECT COUNT(*) FROM tasks WHERE state=?", (state,)
            ).fetchone()
        else:
            row = self._db().execute("SELECT COUNT(*) FROM tasks").fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _exists(self, task_id: str) -> bool:
        row = self._db().execute(
            "SELECT 1 FROM tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        return row is not None

    @staticmethod
    def _row_to_task(row: tuple) -> Task:
        return Task(
            task_id=row[0],
            prompt=row[1],
            state=row[2],
            agent=row[3],
            model=row[4],
            created_at=row[5],
            started_at=row[6],
            finished_at=row[7],
            result=row[8],
            error=row[9],
            metadata=json.loads(row[10]),
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
