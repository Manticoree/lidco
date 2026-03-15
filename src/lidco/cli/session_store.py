"""Session persistence for resume-after-crash — Task 285.

Saves conversation history + metadata to ``.lidco/sessions/<session_id>.json``.
A ``lidco --resume SESSION_ID`` load restores the history into the orchestrator
without replaying tool calls.

Usage::

    store = SessionStore()
    sid = store.save(session_id, history, metadata)
    data = store.load(sid)
    store.list_sessions()
    store.delete(sid)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SESSIONS_DIR = Path(".lidco") / "sessions"


class SessionStore:
    """Persists and retrieves conversation sessions."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base = base_dir or Path.cwd() / ".lidco" / "sessions"

    def _ensure_dir(self) -> None:
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self._base / f"{session_id}.json"

    def save(
        self,
        history: list[dict[str, Any]],
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Persist *history* and return the session ID.

        If *session_id* is not supplied, a new UUID-based ID is generated.
        """
        self._ensure_dir()
        sid = session_id or uuid.uuid4().hex[:12]
        payload: dict[str, Any] = {
            "session_id": sid,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "history": history,
            "metadata": metadata or {},
        }
        self._path(sid).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("SessionStore: saved session '%s' (%d messages)", sid, len(history))
        return sid

    def load(self, session_id: str) -> dict[str, Any] | None:
        """Load a saved session by ID.

        Returns the raw dict (with ``history``, ``metadata``, etc.) or
        ``None`` if the session does not exist.
        """
        p = self._path(session_id)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("SessionStore: failed to load '%s': %s", session_id, exc)
            return None

    def list_sessions(self) -> list[dict[str, Any]]:
        """Return a summary list of all saved sessions, newest first.

        Each entry: ``{"session_id": ..., "saved_at": ..., "message_count": ...}``.
        """
        if not self._base.exists():
            return []
        sessions: list[dict[str, Any]] = []
        for p in sorted(self._base.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": data.get("session_id", p.stem),
                    "saved_at": data.get("saved_at", ""),
                    "message_count": len(data.get("history", [])),
                    "metadata": data.get("metadata", {}),
                })
            except Exception:
                pass
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a saved session. Returns True if it existed."""
        p = self._path(session_id)
        if p.exists():
            p.unlink()
            return True
        return False

    def find_by_name(self, name: str) -> dict[str, Any] | None:
        """Find the most recent session whose metadata contains ``name``.

        Searches ``metadata.name`` field. Returns the raw session dict or ``None``.
        """
        if not self._base.exists():
            return None
        for p in sorted(self._base.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("metadata", {}).get("name") == name:
                    return data
            except Exception:
                pass
        return None

    def fork(self, parent_id: str, fork_name: str | None = None) -> str | None:
        """Create a fork of an existing session.

        Copies the parent history into a new session with ``fork_of`` metadata.
        Returns the new fork session ID, or ``None`` if the parent was not found.
        """
        parent = self.load(parent_id)
        if parent is None:
            return None
        fork_meta: dict[str, Any] = {
            **parent.get("metadata", {}),
            "fork_of": parent_id,
        }
        if fork_name:
            fork_meta["name"] = fork_name
        history = parent.get("history", [])
        fork_id = self.save(history, metadata=fork_meta)
        logger.info("SessionStore: forked '%s' → '%s'", parent_id, fork_id)
        return fork_id

    def search(
        self,
        query: str = "",
        since_days: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search saved sessions by content and/or recency.

        Args:
            query: Text to search for in history message content (case-insensitive).
            since_days: Only return sessions saved within this many days.

        Returns:
            List of summary dicts (session_id, saved_at, message_count, metadata,
            first_user_message) ordered newest-first.
        """
        import datetime as _dt

        if not self._base.exists():
            return []

        cutoff: _dt.datetime | None = None
        if since_days is not None:
            cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=since_days)

        results: list[dict[str, Any]] = []
        for p in sorted(self._base.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue

            saved_at_str = data.get("saved_at", "")
            if cutoff is not None and saved_at_str:
                try:
                    saved_dt = datetime.fromisoformat(saved_at_str)
                    if saved_dt < cutoff:
                        continue
                except Exception:
                    pass

            history = data.get("history", [])
            if query:
                q = query.lower()
                if not any(q in str(m.get("content", "")).lower() for m in history):
                    continue

            first_user = next(
                (str(m.get("content", ""))[:120] for m in history if m.get("role") == "user"),
                "",
            )
            results.append({
                "session_id": data.get("session_id", p.stem),
                "saved_at": saved_at_str,
                "message_count": len(history),
                "metadata": data.get("metadata", {}),
                "first_user_message": first_user,
            })
        return results
