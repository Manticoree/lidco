"""Resume manager — list, resume, and summarise persisted sessions."""
from __future__ import annotations

from datetime import datetime, timezone

from lidco.session.loader import SessionLoader
from lidco.session.persister import SessionPersister


class ResumeManager:
    """High-level facade for resuming saved sessions."""

    def __init__(self, persister: SessionPersister, loader: SessionLoader) -> None:
        self._persister = persister
        self._loader = loader

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_resumable(self, limit: int = 10) -> list[dict]:
        """Return up to *limit* sessions sorted by ``updated_at`` desc."""
        all_sessions = self._persister.list_sessions()  # already sorted desc
        return all_sessions[:limit]

    def get_last_session(self) -> dict | None:
        """Return the most-recently-updated session, or ``None``."""
        sessions = self._persister.list_sessions()
        if not sessions:
            return None
        last = sessions[0]
        return self._loader.load(last["id"])

    def resume(self, session_id: str) -> dict | None:
        """Load a session and touch its ``updated_at`` timestamp.

        Returns the full session dict, or ``None`` if not found.
        """
        session = self._loader.load(session_id)
        if session is None:
            return None

        # Touch updated_at by re-saving with the same data.
        self._persister.save(
            session_id=session["id"],
            messages=session["messages"],
            config=session.get("config"),
            tool_state=session.get("tool_state"),
            metadata=session.get("metadata"),
        )

        # Re-load to get the fresh updated_at.
        return self._loader.load(session_id)

    def create_summary(self, session_id: str) -> str:
        """Generate a human-readable text summary of a session."""
        session = self._loader.load(session_id)
        if session is None:
            return f"Session '{session_id}' not found."

        messages: list[dict] = session.get("messages") or []
        msg_count = len(messages)

        # Role breakdown
        roles: dict[str, int] = {}
        for msg in messages:
            role = msg.get("role", "unknown")
            roles = {**roles, role: roles.get(role, 0) + 1}
        role_parts = ", ".join(f"{r}: {c}" for r, c in sorted(roles.items()))

        # Duration
        created = session.get("created_at", "")
        updated = session.get("updated_at", "")
        duration_str = _format_duration(created, updated)

        lines = [
            f"Session: {session_id}",
            f"Messages: {msg_count} ({role_parts})",
            f"Created: {created}",
            f"Updated: {updated}",
            f"Duration: {duration_str}",
        ]
        return "\n".join(lines)

    def detect_conflicts(self, session_id: str) -> list[str]:
        """Check for potential issues when resuming a session.

        Returns a list of human-readable conflict descriptions (empty if OK).
        """
        session = self._loader.load(session_id)
        if session is None:
            return [f"Session '{session_id}' not found"]

        conflicts: list[str] = []

        # Check integrity via loader
        valid, errors = self._loader.validate_integrity(session_id)
        if not valid:
            conflicts.extend(errors)

        # Stale config warning
        config = session.get("config")
        if config is None:
            conflicts.append("Session has no saved config — defaults will be used")

        # Empty messages
        messages = session.get("messages") or []
        if not messages:
            conflicts.append("Session has no messages")

        return conflicts


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _format_duration(start_iso: str, end_iso: str) -> str:
    """Return a human-friendly duration string, or 'unknown'."""
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
        delta = end - start
        total_secs = int(delta.total_seconds())
        if total_secs < 0:
            return "unknown"
        hours, remainder = divmod(total_secs, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
    except (ValueError, TypeError):
        return "unknown"
