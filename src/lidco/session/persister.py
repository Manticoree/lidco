"""Session persistence via SQLite — save, list, delete sessions."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


class SessionPersister:
    """Persist session data (messages, config, tool state) to SQLite."""

    _CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS sessions (
            id         TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            config     TEXT,
            messages   TEXT,
            tool_state TEXT,
            metadata   TEXT
        )
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(self._CREATE_TABLE)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(
        self,
        session_id: str,
        messages: list[dict],
        config: dict | None = None,
        tool_state: dict | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Save or overwrite a full session.  Returns *session_id*."""
        now = _now_iso()
        row = self._conn.execute(
            "SELECT created_at FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        created = row["created_at"] if row else now

        self._conn.execute(
            """
            INSERT OR REPLACE INTO sessions
                (id, created_at, updated_at, config, messages, tool_state, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                created,
                now,
                json.dumps(config) if config is not None else None,
                json.dumps(messages),
                json.dumps(tool_state) if tool_state is not None else None,
                json.dumps(metadata) if metadata is not None else None,
            ),
        )
        self._conn.commit()
        return session_id

    def save_incremental(self, session_id: str, new_messages: list[dict]) -> bool:
        """Append *new_messages* to an existing session.  Returns ``True`` on success."""
        row = self._conn.execute(
            "SELECT messages FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return False

        existing: list[dict] = json.loads(row["messages"]) if row["messages"] else []
        merged = [*existing, *new_messages]
        self._conn.execute(
            "UPDATE sessions SET messages = ?, updated_at = ? WHERE id = ?",
            (json.dumps(merged), _now_iso(), session_id),
        )
        self._conn.commit()
        return True

    def exists(self, session_id: str) -> bool:
        """Return whether *session_id* exists in the store."""
        row = self._conn.execute(
            "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return row is not None

    def delete(self, session_id: str) -> bool:
        """Delete a session.  Returns ``True`` if a row was removed."""
        cur = self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def list_sessions(self) -> list[dict]:
        """Return lightweight info for every saved session."""
        rows = self._conn.execute(
            "SELECT id, created_at, updated_at, messages FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        results: list[dict] = []
        for r in rows:
            msgs: list[dict] = json.loads(r["messages"]) if r["messages"] else []
            results.append(
                {
                    "id": r["id"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "message_count": len(msgs),
                }
            )
        return results

    def get_raw(self, session_id: str) -> dict | None:
        """Return the full raw row as a dict (used by loader / gc)."""
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "config": row["config"],
            "messages": row["messages"],
            "tool_state": row["tool_state"],
            "metadata": row["metadata"],
        }

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
