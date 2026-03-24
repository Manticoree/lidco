"""Persistent cross-session agent memory -- stores facts the agent learns."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class AgentMemory:
    """A single memory entry stored by the agent."""

    id: str
    content: str
    tags: list[str]
    created_at: float
    last_used: float
    use_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentMemory:
        return cls(**d)


class AgentMemoryStore:
    """SQLite-backed store for persistent agent memories."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            db_path = Path(".lidco") / "agent_memory.db"
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL,
                    last_used REAL NOT NULL,
                    use_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_memory(self, row: sqlite3.Row) -> AgentMemory:
        return AgentMemory(
            id=row["id"],
            content=row["content"],
            tags=json.loads(row["tags"]),
            created_at=row["created_at"],
            last_used=row["last_used"],
            use_count=row["use_count"],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, content: str, tags: list[str] | None = None) -> AgentMemory:
        """Store a new memory and return it."""
        memory = AgentMemory(
            id=str(uuid.uuid4())[:8],
            content=content.strip(),
            tags=tags or [],
            created_at=time.time(),
            last_used=time.time(),
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?)",
                (
                    memory.id,
                    memory.content,
                    json.dumps(memory.tags),
                    memory.created_at,
                    memory.last_used,
                    memory.use_count,
                ),
            )
        return memory

    def search(self, query: str, limit: int = 10) -> list[AgentMemory]:
        """Simple keyword search across content and tags."""
        words = query.lower().split()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY last_used DESC LIMIT 200"
            ).fetchall()
        results: list[tuple[int, AgentMemory]] = []
        for row in rows:
            text = (row["content"] + " " + row["tags"]).lower()
            score = sum(1 for w in words if w in text)
            if score > 0:
                results.append((score, self._row_to_memory(row)))
        results.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in results[:limit]]

    def list(self, limit: int = 20) -> list[AgentMemory]:
        """Return the most recently used memories."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY last_used DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def get(self, memory_id: str) -> AgentMemory | None:
        """Retrieve a single memory by id, or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
        return self._row_to_memory(row) if row else None

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by id. Returns True if it existed."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cur.rowcount > 0

    def clear(self) -> int:
        """Delete all memories. Returns count of removed entries."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM memories")
        return cur.rowcount

    def touch(self, memory_id: str) -> None:
        """Update last_used timestamp and increment use_count."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE memories SET last_used = ?, use_count = use_count + 1 WHERE id = ?",
                (time.time(), memory_id),
            )

    def format_for_prompt(self, memories: list[AgentMemory]) -> str:
        """Format memories as a system-prompt block."""
        if not memories:
            return ""
        lines = ["## Agent Memory\n"]
        for m in memories:
            tag_str = f" [{', '.join(m.tags)}]" if m.tags else ""
            lines.append(f"- {m.content}{tag_str}")
        return "\n".join(lines)
