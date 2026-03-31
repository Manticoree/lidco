"""SQLite-backed vector storage with cosine similarity search."""

from __future__ import annotations

import json
import math
import sqlite3
import time
from dataclasses import dataclass, field


@dataclass
class VectorEntry:
    """A stored vector entry."""

    id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    chunk_type: str
    name: str
    embedding: list[float]
    updated_at: float = 0.0

    def __post_init__(self) -> None:
        if self.updated_at == 0.0:
            object.__setattr__(self, "updated_at", time.time())


class VectorStore:
    """SQLite-backed vector store with cosine similarity search."""

    def __init__(self, db_path: str = ":memory:", namespace: str = "default") -> None:
        self.db_path = db_path
        self.namespace = namespace
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS vectors (
                id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                file_path TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                content TEXT NOT NULL,
                chunk_type TEXT NOT NULL,
                name TEXT NOT NULL,
                embedding BLOB NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_vectors_ns_fp
            ON vectors (namespace, file_path)
            """
        )
        self._conn.commit()

    def upsert(self, entry: VectorEntry) -> None:
        """Insert or replace a vector entry."""
        emb_blob = json.dumps(entry.embedding)
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO vectors
                (id, namespace, file_path, start_line, end_line, content,
                 chunk_type, name, embedding, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                self.namespace,
                entry.file_path,
                entry.start_line,
                entry.end_line,
                entry.content,
                entry.chunk_type,
                entry.name,
                emb_blob,
                entry.updated_at,
            ),
        )
        self._conn.commit()

    def upsert_batch(self, entries: list[VectorEntry]) -> None:
        """Batch upsert in a single transaction."""
        cur = self._conn.cursor()
        rows = [
            (
                e.id,
                self.namespace,
                e.file_path,
                e.start_line,
                e.end_line,
                e.content,
                e.chunk_type,
                e.name,
                json.dumps(e.embedding),
                e.updated_at,
            )
            for e in entries
        ]
        cur.executemany(
            """
            INSERT OR REPLACE INTO vectors
                (id, namespace, file_path, start_line, end_line, content,
                 chunk_type, name, embedding, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()

    def search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[tuple[VectorEntry, float]]:
        """Search by cosine similarity, return top-k results with scores."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM vectors WHERE namespace = ?", (self.namespace,)
        )
        rows = cur.fetchall()

        results: list[tuple[VectorEntry, float]] = []
        for row in rows:
            emb = json.loads(row["embedding"])
            score = _cosine_similarity(query_embedding, emb)
            entry = VectorEntry(
                id=row["id"],
                file_path=row["file_path"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                content=row["content"],
                chunk_type=row["chunk_type"],
                name=row["name"],
                embedding=emb,
                updated_at=row["updated_at"],
            )
            results.append((entry, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def delete_by_file(self, file_path: str) -> int:
        """Delete all entries for *file_path*, return count deleted."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM vectors WHERE namespace = ? AND file_path = ?",
            (self.namespace, file_path),
        )
        count = cur.fetchone()[0]
        cur.execute(
            "DELETE FROM vectors WHERE namespace = ? AND file_path = ?",
            (self.namespace, file_path),
        )
        self._conn.commit()
        return count

    def get_by_file(self, file_path: str) -> list[VectorEntry]:
        """Get all entries for a file."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM vectors WHERE namespace = ? AND file_path = ?",
            (self.namespace, file_path),
        )
        rows = cur.fetchall()
        return [
            VectorEntry(
                id=row["id"],
                file_path=row["file_path"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                content=row["content"],
                chunk_type=row["chunk_type"],
                name=row["name"],
                embedding=json.loads(row["embedding"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def count(self) -> int:
        """Total entries in namespace."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM vectors WHERE namespace = ?", (self.namespace,)
        )
        return cur.fetchone()[0]

    def clear(self) -> None:
        """Delete all entries in namespace."""
        cur = self._conn.cursor()
        cur.execute("DELETE FROM vectors WHERE namespace = ?", (self.namespace,))
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
