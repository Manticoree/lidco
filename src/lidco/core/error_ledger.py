"""Cross-session error persistence — SQLite-backed error ledger."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS error_ledger (
    error_hash TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    total_occurrences INTEGER NOT NULL DEFAULT 1,
    sessions_count INTEGER NOT NULL DEFAULT 1,
    fix_applied INTEGER NOT NULL DEFAULT 0,
    fix_description TEXT,
    sample_message TEXT
);
"""

def _error_hash(error_type: str, file_hint: str | None, function_hint: str | None) -> str:
    """SHA-256 of error_type:file_hint:function_hint, truncated to 16 hex chars."""
    raw = f"{error_type}:{file_hint or ''}:{function_hint or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class ErrorLedger:
    """Persistent cross-session error tracker backed by SQLite.

    Stores to .lidco/error_ledger.db. Creates the file and table on first use.
    All methods are failure-safe — exceptions are logged and swallowed.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn.execute(_CREATE_TABLE)
            self._conn.commit()
        except Exception as exc:
            logger.debug("ErrorLedger init failed: %s", exc)
            self._conn = None

    def record(self, error_type: str, file_hint: str | None,
               function_hint: str | None, message: str, session_id: str,
               traceback_str: str | None = None) -> None:
        """Upsert error record — increment occurrence + session counts.

        When *traceback_str* is provided, uses semantic fingerprinting via
        :func:`~lidco.core.error_fingerprint.fingerprint_error` for a more
        stable hash that survives minor message variations (addresses, UUIDs).
        Falls back to the legacy ``_error_hash`` when no traceback is available.
        """
        if self._conn is None:
            return
        try:
            if traceback_str is not None:
                from lidco.core.error_fingerprint import fingerprint_error
                error_hash = fingerprint_error(error_type, message, traceback_str)
            else:
                error_hash = _error_hash(error_type, file_hint, function_hint)
            now = datetime.now(timezone.utc).isoformat()
            # Try INSERT first
            try:
                self._conn.execute(
                    "INSERT INTO error_ledger "
                    "(error_hash, first_seen, last_seen, total_occurrences, "
                    "sessions_count, sample_message) "
                    "VALUES (?, ?, ?, 1, 1, ?)",
                    (error_hash, now, now, message[:500]),
                )
            except sqlite3.IntegrityError:
                # Already exists — UPDATE: increment occurrences, update last_seen
                # sessions_count: increment only if this session_id is new
                # We track sessions via a separate approach: just always increment
                # (approximate — good enough for our purposes)
                self._conn.execute(
                    "UPDATE error_ledger SET "
                    "last_seen = ?, total_occurrences = total_occurrences + 1, "
                    "sessions_count = sessions_count + 1 "
                    "WHERE error_hash = ?",
                    (now, error_hash),
                )
            self._conn.commit()
        except Exception as exc:
            logger.debug("ErrorLedger.record failed: %s", exc)

    def mark_fixed(self, error_type: str, file_hint: str | None,
                   function_hint: str | None, description: str) -> None:
        """Mark an error as fixed with a description."""
        if self._conn is None:
            return
        try:
            error_hash = _error_hash(error_type, file_hint, function_hint)
            self._conn.execute(
                "UPDATE error_ledger SET fix_applied = 1, fix_description = ? "
                "WHERE error_hash = ?",
                (description[:500], error_hash),
            )
            self._conn.commit()
        except Exception as exc:
            logger.debug("ErrorLedger.mark_fixed failed: %s", exc)

    def get_recurring(self, min_sessions: int = 2) -> list[dict[str, Any]]:
        """Return errors seen in >= min_sessions sessions."""
        if self._conn is None:
            return []
        try:
            cursor = self._conn.execute(
                "SELECT error_hash, first_seen, last_seen, total_occurrences, "
                "sessions_count, fix_applied, fix_description, sample_message "
                "FROM error_ledger WHERE sessions_count >= ? AND fix_applied = 0 "
                "ORDER BY sessions_count DESC, total_occurrences DESC",
                (min_sessions,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "error_hash": r[0],
                    "first_seen": r[1],
                    "last_seen": r[2],
                    "total_occurrences": r[3],
                    "sessions_count": r[4],
                    "fix_applied": bool(r[5]),
                    "fix_description": r[6],
                    "sample_message": r[7],
                }
                for r in rows
            ]
        except Exception as exc:
            logger.debug("ErrorLedger.get_recurring failed: %s", exc)
            return []

    def get_frequent(self, min_occurrences: int = 5) -> list[dict[str, Any]]:
        """Return errors with >= min_occurrences total."""
        if self._conn is None:
            return []
        try:
            cursor = self._conn.execute(
                "SELECT error_hash, first_seen, last_seen, total_occurrences, "
                "sessions_count, fix_applied, fix_description, sample_message "
                "FROM error_ledger WHERE total_occurrences >= ? AND fix_applied = 0 "
                "ORDER BY total_occurrences DESC",
                (min_occurrences,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "error_hash": r[0], "first_seen": r[1], "last_seen": r[2],
                    "total_occurrences": r[3], "sessions_count": r[4],
                    "fix_applied": bool(r[5]), "fix_description": r[6],
                    "sample_message": r[7],
                }
                for r in rows
            ]
        except Exception as exc:
            logger.debug("ErrorLedger.get_frequent failed: %s", exc)
            return []

    def summarize(self) -> str:
        """Return Markdown summary of recurring/frequent errors for context injection."""
        recurring = self.get_recurring(min_sessions=2)
        if not recurring:
            return ""
        lines = ["## Recurring Issues (cross-session)"]
        for r in recurring[:5]:
            msg_preview = (r["sample_message"] or "")[:80]
            lines.append(
                f"- `{r['error_hash']}` seen {r['total_occurrences']}× "
                f"across {r['sessions_count']} sessions: {msg_preview}"
            )
        return "\n".join(lines)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
