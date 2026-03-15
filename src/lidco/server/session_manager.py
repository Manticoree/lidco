"""Multi-session manager — Task 306.

Manages multiple concurrent LIDCO sessions identified by session IDs.
Each session is an independent context (conversation history, tools, config).

Usage::

    manager = SessionManager()
    sid = manager.create()
    session = manager.get(sid)
    manager.close(sid)
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.core.session import Session

logger = logging.getLogger(__name__)

_MAX_SESSIONS = 20


@dataclass
class SessionInfo:
    """Metadata about a managed session."""

    session_id: str
    created_at: float
    last_active: float
    turn_count: int = 0
    tags: list[str] = field(default_factory=list)

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_active


class SessionNotFoundError(Exception):
    """Raised when a session ID is not found."""


class SessionLimitError(Exception):
    """Raised when the session limit is exceeded."""


class SessionManager:
    """Manages multiple LIDCO sessions.

    Args:
        max_sessions: Maximum concurrent sessions (default 20).
        session_factory: Callable that creates a new Session. If None,
            sessions must be injected via ``inject()``.
    """

    def __init__(
        self,
        max_sessions: int = _MAX_SESSIONS,
        session_factory: Any = None,
    ) -> None:
        self._max = max_sessions
        self._factory = session_factory
        self._sessions: dict[str, "Session"] = {}
        self._info: dict[str, SessionInfo] = {}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, tags: list[str] | None = None) -> str:
        """Create a new session and return its ID.

        Raises:
            SessionLimitError: if ``max_sessions`` is reached.
        """
        if len(self._info) >= self._max:
            raise SessionLimitError(
                f"Maximum of {self._max} concurrent sessions reached."
            )
        sid = str(uuid.uuid4())
        now = time.time()
        self._info[sid] = SessionInfo(
            session_id=sid,
            created_at=now,
            last_active=now,
            tags=list(tags or []),
        )
        if self._factory is not None:
            self._sessions[sid] = self._factory()
        logger.info("SessionManager: created session %s", sid)
        return sid

    def inject(self, session: "Session", session_id: str | None = None) -> str:
        """Register an externally-created session. Returns its ID."""
        if len(self._info) >= self._max:
            raise SessionLimitError(
                f"Maximum of {self._max} concurrent sessions reached."
            )
        sid = session_id or str(uuid.uuid4())
        now = time.time()
        self._sessions[sid] = session
        self._info[sid] = SessionInfo(
            session_id=sid,
            created_at=now,
            last_active=now,
        )
        return sid

    def get(self, session_id: str) -> "Session":
        """Return the session by ID.

        Raises:
            SessionNotFoundError: if not found.
        """
        if session_id not in self._sessions:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")
        self._touch(session_id)
        return self._sessions[session_id]

    def close(self, session_id: str) -> bool:
        """Close and remove a session. Returns True if it existed."""
        if session_id not in self._sessions:
            return False
        session = self._sessions.pop(session_id)
        self._info.pop(session_id, None)
        # Best-effort cleanup
        try:
            close = getattr(session, "close", None) or getattr(session, "stop", None)
            if callable(close):
                import asyncio
                if asyncio.iscoroutinefunction(close):
                    asyncio.get_event_loop().run_until_complete(close())
                else:
                    close()
        except Exception as exc:
            logger.warning("SessionManager: error closing session %s: %s", session_id, exc)
        logger.info("SessionManager: closed session %s", session_id)
        return True

    def close_all(self) -> int:
        """Close all sessions. Returns count closed."""
        ids = list(self._sessions.keys())
        for sid in ids:
            self.close(sid)
        return len(ids)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_sessions(self) -> list[SessionInfo]:
        """Return info for all active sessions sorted by creation time."""
        return sorted(self._info.values(), key=lambda s: s.created_at)

    def info(self, session_id: str) -> SessionInfo:
        """Return metadata for a session."""
        if session_id not in self._info:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")
        return self._info[session_id]

    def count(self) -> int:
        """Return number of active sessions."""
        return len(self._info)

    def record_turn(self, session_id: str) -> None:
        """Increment turn counter and update last_active."""
        if session_id in self._info:
            self._info[session_id].turn_count += 1
            self._touch(session_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _touch(self, session_id: str) -> None:
        if session_id in self._info:
            self._info[session_id].last_active = time.time()
