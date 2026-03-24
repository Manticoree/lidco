import json
import sqlite3
import time
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class SessionRecord:
    session_id: str
    topic: str
    started_at: float
    ended_at: float
    turn_count: int
    summary: str
    tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class HistorySearchResult:
    records: list
    total: int
    query: str


class SessionHistoryStore:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path(".lidco") / "session_history.db"
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Create DB and tables lazily."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    topic TEXT,
                    started_at REAL,
                    ended_at REAL,
                    turn_count INTEGER,
                    summary TEXT,
                    tags TEXT,
                    metadata TEXT
                )
            """)

    def save(self, record: SessionRecord) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                record.session_id, record.topic,
                record.started_at, record.ended_at,
                record.turn_count, record.summary,
                json.dumps(record.tags), json.dumps(record.metadata)
            ))

    def list(self, limit: int = 20, offset: int = 0) -> list:
        """Returns newest-first."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def search(self, query: str, limit: int = 10) -> HistorySearchResult:
        """LIKE-based search across topic, summary, tags."""
        like = f"%{query}%"
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM sessions
                   WHERE topic LIKE ? OR summary LIKE ? OR tags LIKE ?
                   ORDER BY started_at DESC LIMIT ?""",
                (like, like, like, limit)
            ).fetchall()
        records = [self._row_to_record(r) for r in rows]
        return HistorySearchResult(records=records, total=len(records), query=query)

    def get(self, session_id: str) -> Optional[SessionRecord]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def delete(self, session_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM sessions WHERE session_id=?", (session_id,)
            )
        return cur.rowcount > 0

    def resume_context(self, session_id: str) -> str:
        """Return formatted summary for system prompt injection."""
        record = self.get(session_id)
        if not record:
            return ""
        lines = [
            f"## Resumed Session: {record.topic}",
            f"Started: {time.strftime('%Y-%m-%d %H:%M', time.localtime(record.started_at))}",
            f"Turns: {record.turn_count}",
            f"Summary: {record.summary}",
        ]
        if record.tags:
            lines.append(f"Tags: {', '.join(record.tags)}")
        return "\n".join(lines)

    def auto_topic(self, messages: list) -> str:
        """Extract topic from first user message (first 10 words)."""
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        p.get("text", "") for p in content if isinstance(p, dict)
                    )
                words = re.sub(r'[^\w\s]', '', content).split()[:10]
                return " ".join(words) if words else "Untitled Session"
        return "Untitled Session"

    def _row_to_record(self, row) -> SessionRecord:
        return SessionRecord(
            session_id=row[0], topic=row[1],
            started_at=row[2], ended_at=row[3],
            turn_count=row[4], summary=row[5],
            tags=json.loads(row[6] or "[]"),
            metadata=json.loads(row[7] or "{}")
        )
