"""CrashRecovery -- detect unclean exits and restore from checkpoints (stdlib only)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from lidco.resilience.auto_checkpoint import AutoCheckpoint


@dataclass
class RecoveryInfo:
    """Information about a potential crash and recovery options."""

    crash_detected: bool
    last_session_id: Optional[str] = None
    checkpoint: Optional[dict] = None
    recovery_actions: list[str] = field(default_factory=list)


class CrashRecovery:
    """Track session lifecycle and recover from unclean shutdowns."""

    def __init__(self, checkpoint_store: AutoCheckpoint) -> None:
        self._checkpoint_store = checkpoint_store
        # session_id -> {"started_at": float, "ended": bool}
        self._sessions: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mark_session_start(self, session_id: str) -> None:
        """Record that *session_id* has started."""
        self._sessions[session_id] = {
            "started_at": time.time(),
            "ended": False,
        }

    def mark_session_end(self, session_id: str) -> None:
        """Record a clean exit for *session_id*."""
        if session_id in self._sessions:
            self._sessions[session_id]["ended"] = True

    def detect_crash(self) -> RecoveryInfo:
        """Check whether any tracked session ended without a clean exit."""
        for sid in reversed(list(self._sessions.keys())):
            info = self._sessions[sid]
            if not info["ended"]:
                latest = self._checkpoint_store.latest()
                cp_data = latest.data if latest else None
                actions: list[str] = []
                if cp_data is not None:
                    actions.append("restore_from_checkpoint")
                actions.append("start_new_session")
                return RecoveryInfo(
                    crash_detected=True,
                    last_session_id=sid,
                    checkpoint=cp_data,
                    recovery_actions=actions,
                )
        return RecoveryInfo(crash_detected=False)

    def recover(self) -> Optional[dict]:
        """Attempt to restore data from the latest checkpoint, or *None*."""
        latest = self._checkpoint_store.latest()
        if latest is not None:
            return latest.data
        return None

    def cleanup_stale(self, max_age_seconds: float = 86400) -> None:
        """Remove session markers older than *max_age_seconds*."""
        now = time.time()
        stale = [
            sid
            for sid, info in self._sessions.items()
            if (now - info["started_at"]) > max_age_seconds
        ]
        for sid in stale:
            del self._sessions[sid]
