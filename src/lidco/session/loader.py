"""Session loading and integrity validation."""
from __future__ import annotations

import json
import sqlite3


class SessionLoader:
    """Load and validate persisted sessions from SQLite."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, session_id: str) -> dict | None:
        """Load a full session by *session_id*.

        Returns a dict with keys: id, messages, config, tool_state,
        metadata, created_at, updated_at — or ``None`` if not found.
        """
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)

    def load_partial(self, session_id: str, last_n: int = 10) -> dict | None:
        """Load a session but keep only the last *last_n* messages."""
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        result = _row_to_dict(row)
        messages = result.get("messages") or []
        result = {**result, "messages": messages[-last_n:]}
        return result

    def validate_integrity(self, session_id: str) -> tuple[bool, list[str]]:
        """Check JSON validity and required fields for *session_id*.

        Returns ``(is_valid, list_of_errors)``.
        """
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return False, [f"Session '{session_id}' not found"]

        errors: list[str] = []

        # messages must be valid JSON list
        try:
            msgs = json.loads(row["messages"]) if row["messages"] else []
            if not isinstance(msgs, list):
                errors.append("messages is not a JSON array")
        except (json.JSONDecodeError, TypeError) as exc:
            errors.append(f"messages JSON invalid: {exc}")

        # config — optional but must be valid JSON if present
        if row["config"] is not None:
            try:
                cfg = json.loads(row["config"])
                if not isinstance(cfg, dict):
                    errors.append("config is not a JSON object")
            except (json.JSONDecodeError, TypeError) as exc:
                errors.append(f"config JSON invalid: {exc}")

        # tool_state — optional but must be valid JSON if present
        if row["tool_state"] is not None:
            try:
                ts = json.loads(row["tool_state"])
                if not isinstance(ts, dict):
                    errors.append("tool_state is not a JSON object")
            except (json.JSONDecodeError, TypeError) as exc:
                errors.append(f"tool_state JSON invalid: {exc}")

        # metadata — optional but must be valid JSON if present
        if row["metadata"] is not None:
            try:
                md = json.loads(row["metadata"])
                if not isinstance(md, dict):
                    errors.append("metadata is not a JSON object")
            except (json.JSONDecodeError, TypeError) as exc:
                errors.append(f"metadata JSON invalid: {exc}")

        # required fields
        if not row["id"]:
            errors.append("id is empty")
        if not row["created_at"]:
            errors.append("created_at is missing")
        if not row["updated_at"]:
            errors.append("updated_at is missing")

        return (len(errors) == 0, errors)

    def migrate_schema(self, session_id: str, target_version: int = 1) -> bool:
        """Placeholder for future schema migrations.

        Currently only version 1 exists, so this is a no-op that returns
        ``True`` if the session exists.
        """
        row = self._conn.execute(
            "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return False
        if target_version < 1:
            return False
        # Version 1 is the current (and only) schema — nothing to do.
        return True

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _safe_json_load(raw: str | None, fallback=None):
    """Parse *raw* as JSON, returning *fallback* on failure or ``None``."""
    if raw is None:
        return fallback
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return fallback


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "messages": _safe_json_load(row["messages"], []),
        "config": _safe_json_load(row["config"]),
        "tool_state": _safe_json_load(row["tool_state"]),
        "metadata": _safe_json_load(row["metadata"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
