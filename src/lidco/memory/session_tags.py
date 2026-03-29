"""SessionTagStore — SQLite-backed session tagging (Task 700)."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SessionTag:
    session_id: str
    tags: list[str]
    attributes: dict[str, str]
    created_at: str


class SessionTagStore:
    """SQLite-backed store for session tags and attributes."""

    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS session_tags (
                session_id TEXT PRIMARY KEY,
                tags TEXT NOT NULL DEFAULT '[]',
                attributes TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def tag(self, session_id: str, tags: list[str], attributes: dict[str, str] | None = None) -> None:
        """Add tags to session. Idempotent -- same tag added twice is fine."""
        attrs = attributes or {}
        existing = self.get(session_id)
        if existing is not None:
            merged_tags = list(dict.fromkeys(existing.tags + tags))
            merged_attrs = {**existing.attributes, **attrs}
            self._conn.execute(
                "UPDATE session_tags SET tags = ?, attributes = ? WHERE session_id = ?",
                (json.dumps(merged_tags), json.dumps(merged_attrs), session_id),
            )
        else:
            now = datetime.now(timezone.utc).isoformat()
            unique_tags = list(dict.fromkeys(tags))
            self._conn.execute(
                "INSERT INTO session_tags (session_id, tags, attributes, created_at) VALUES (?, ?, ?, ?)",
                (session_id, json.dumps(unique_tags), json.dumps(attrs), now),
            )
        self._conn.commit()

    def untag(self, session_id: str, tag: str) -> None:
        """Remove a tag from a session."""
        existing = self.get(session_id)
        if existing is None:
            return
        new_tags = [t for t in existing.tags if t != tag]
        self._conn.execute(
            "UPDATE session_tags SET tags = ? WHERE session_id = ?",
            (json.dumps(new_tags), session_id),
        )
        self._conn.commit()

    def get(self, session_id: str) -> Optional[SessionTag]:
        """Get session tag data by session_id."""
        row = self._conn.execute(
            "SELECT * FROM session_tags WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_tag(row)

    def search(self, query: str) -> list[SessionTag]:
        """Return sessions whose tags contain query (case-insensitive substring)."""
        query_lower = query.lower()
        rows = self._conn.execute("SELECT * FROM session_tags ORDER BY created_at DESC").fetchall()
        results: list[SessionTag] = []
        for row in rows:
            tag_obj = self._row_to_tag(row)
            for t in tag_obj.tags:
                if query_lower in t.lower():
                    results.append(tag_obj)
                    break
        return results

    def filter(
        self,
        origin: str | None = None,
        after: str | None = None,
        before: str | None = None,
        agent: str | None = None,
    ) -> list[SessionTag]:
        """Filter by attribute values. None means no filter on that attr."""
        rows = self._conn.execute("SELECT * FROM session_tags ORDER BY created_at DESC").fetchall()
        results: list[SessionTag] = []
        for row in rows:
            tag_obj = self._row_to_tag(row)
            if origin is not None and tag_obj.attributes.get("origin") != origin:
                continue
            if agent is not None and tag_obj.attributes.get("agent") != agent:
                continue
            if after is not None and tag_obj.created_at < after:
                continue
            if before is not None and tag_obj.created_at > before:
                continue
            results.append(tag_obj)
        return results

    def list_all(self) -> list[SessionTag]:
        """List all tagged sessions."""
        rows = self._conn.execute("SELECT * FROM session_tags ORDER BY created_at DESC").fetchall()
        return [self._row_to_tag(row) for row in rows]

    def delete(self, session_id: str) -> None:
        """Delete session tag data."""
        self._conn.execute("DELETE FROM session_tags WHERE session_id = ?", (session_id,))
        self._conn.commit()

    @staticmethod
    def _row_to_tag(row) -> SessionTag:
        return SessionTag(
            session_id=row["session_id"],
            tags=json.loads(row["tags"]),
            attributes=json.loads(row["attributes"]),
            created_at=row["created_at"],
        )
