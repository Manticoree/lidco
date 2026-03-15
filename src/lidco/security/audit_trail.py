"""Full audit trail — Task 322.

Records every agent action (tool calls, LLM completions, decisions) to an
SQLite database with reasoning and timestamps for enterprise compliance.

Usage::

    trail = AuditTrail(db_path=".lidco/audit.db")
    event_id = trail.record(
        event_type="tool_call",
        agent="coder",
        action="bash",
        reasoning="Running tests to verify fix",
        details={"command": "pytest tests/"},
    )
    events = trail.query(agent="coder", limit=20)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(".lidco") / "audit.db"


@dataclass
class AuditEvent:
    """A single recorded audit event."""

    event_id: str
    timestamp: float
    session_id: str
    event_type: str   # tool_call | llm_call | decision | user_message | error
    agent: str
    action: str
    reasoning: str
    details: dict[str, Any]
    outcome: str = ""   # success | failure | pending
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "agent": self.agent,
            "action": self.action,
            "reasoning": self.reasoning,
            "details": self.details,
            "outcome": self.outcome,
            "duration_ms": self.duration_ms,
        }


class AuditTrail:
    """Records and queries agent audit events in SQLite.

    Args:
        db_path: Path to SQLite database file.
        session_id: Identifier for the current session.
    """

    _CREATE_SQL = """
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id     TEXT PRIMARY KEY,
            timestamp    REAL NOT NULL,
            session_id   TEXT NOT NULL,
            event_type   TEXT NOT NULL,
            agent        TEXT NOT NULL,
            action       TEXT NOT NULL,
            reasoning    TEXT NOT NULL DEFAULT '',
            details_json TEXT NOT NULL DEFAULT '{}',
            outcome      TEXT NOT NULL DEFAULT '',
            duration_ms  REAL NOT NULL DEFAULT 0.0
        );
        CREATE INDEX IF NOT EXISTS idx_session ON audit_events(session_id);
        CREATE INDEX IF NOT EXISTS idx_agent   ON audit_events(agent);
        CREATE INDEX IF NOT EXISTS idx_ts      ON audit_events(timestamp);
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        session_id: str | None = None,
    ) -> None:
        self._path = Path(db_path) if db_path else _DEFAULT_DB
        self._session_id = session_id or str(uuid.uuid4())
        self._conn: sqlite3.Connection | None = None

    def _ensure_db(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
            self._conn.executescript(self._CREATE_SQL)
            self._conn.commit()
        return self._conn

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(
        self,
        event_type: str,
        agent: str,
        action: str,
        reasoning: str = "",
        details: dict[str, Any] | None = None,
        outcome: str = "",
        duration_ms: float = 0.0,
        event_id: str | None = None,
    ) -> str:
        """Record an audit event. Returns the event_id."""
        eid = event_id or str(uuid.uuid4())
        conn = self._ensure_db()
        conn.execute(
            """
            INSERT INTO audit_events
                (event_id, timestamp, session_id, event_type, agent, action,
                 reasoning, details_json, outcome, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eid,
                time.time(),
                self._session_id,
                event_type,
                agent,
                action,
                reasoning,
                json.dumps(details or {}),
                outcome,
                duration_ms,
            ),
        )
        conn.commit()
        return eid

    def update_outcome(self, event_id: str, outcome: str, duration_ms: float = 0.0) -> None:
        """Update the outcome of a previously recorded event."""
        conn = self._ensure_db()
        conn.execute(
            "UPDATE audit_events SET outcome=?, duration_ms=? WHERE event_id=?",
            (outcome, duration_ms, event_id),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        session_id: str | None = None,
        agent: str | None = None,
        event_type: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events with optional filters."""
        conn = self._ensure_db()
        wheres: list[str] = []
        params: list[Any] = []

        if session_id:
            wheres.append("session_id = ?")
            params.append(session_id)
        if agent:
            wheres.append("agent = ?")
            params.append(agent)
        if event_type:
            wheres.append("event_type = ?")
            params.append(event_type)
        if since:
            wheres.append("timestamp >= ?")
            params.append(since)

        where_clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        params.append(limit)

        rows = conn.execute(
            f"SELECT * FROM audit_events {where_clause} ORDER BY timestamp DESC LIMIT ?",
            params,
        ).fetchall()

        return [self._row_to_event(row) for row in rows]

    def get(self, event_id: str) -> AuditEvent | None:
        """Return a single event by ID."""
        conn = self._ensure_db()
        row = conn.execute(
            "SELECT * FROM audit_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        return self._row_to_event(row) if row else None

    def count(self, session_id: str | None = None) -> int:
        """Count events, optionally filtered by session."""
        conn = self._ensure_db()
        if session_id:
            row = conn.execute(
                "SELECT COUNT(*) FROM audit_events WHERE session_id = ?", (session_id,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()
        return row[0] if row else 0

    def export_json(self, output_path: Path | None = None) -> str:
        """Export all events as JSON string (and optionally write to file)."""
        events = self.query(limit=10_000)
        data = [e.to_dict() for e in events]
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        if output_path:
            output_path.write_text(json_str, encoding="utf-8")
        return json_str

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_event(row: tuple) -> AuditEvent:
        return AuditEvent(
            event_id=row[0],
            timestamp=row[1],
            session_id=row[2],
            event_type=row[3],
            agent=row[4],
            action=row[5],
            reasoning=row[6],
            details=json.loads(row[7]),
            outcome=row[8],
            duration_ms=row[9],
        )
