"""
Flaky test quarantine — manage flaky test quarantine lifecycle.

Auto-skip, re-enable policy, manual override, notification callbacks.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Sequence


class QuarantineStatus(Enum):
    """Status of a quarantined test."""

    ACTIVE = "active"
    RELEASED = "released"
    MANUAL_OVERRIDE = "manual_override"
    EXPIRED = "expired"


@dataclass
class QuarantineEntry:
    """A quarantined test entry."""

    test_name: str
    status: QuarantineStatus = QuarantineStatus.ACTIVE
    reason: str = ""
    quarantined_at: float = 0.0
    release_after: float = 0.0  # timestamp
    consecutive_passes: int = 0
    passes_to_release: int = 3
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QuarantineSummary:
    """Summary of quarantine state."""

    total: int
    active: int
    released: int
    expired: int
    overridden: int
    entries: list[QuarantineEntry] = field(default_factory=list)


NotifyFn = Callable[[str, QuarantineEntry], None]


class FlakyQuarantine:
    """Manage flaky test quarantine.

    Parameters
    ----------
    store_path : Path | None
        Path to persist quarantine data (JSON). If None, in-memory only.
    default_ttl_seconds : float
        Default quarantine duration (default 7 days).
    passes_to_release : int
        Consecutive passes required to auto-release (default 3).
    """

    def __init__(
        self,
        *,
        store_path: Path | None = None,
        default_ttl_seconds: float = 7 * 24 * 3600,
        passes_to_release: int = 3,
    ) -> None:
        self._store_path = store_path
        self._default_ttl = default_ttl_seconds
        self._passes_to_release = max(1, passes_to_release)
        self._entries: dict[str, QuarantineEntry] = {}
        self._listeners: list[NotifyFn] = []
        if store_path and store_path.exists():
            self._load()

    # ------------------------------------------------------------------
    # Notification
    # ------------------------------------------------------------------

    def add_listener(self, fn: NotifyFn) -> None:
        """Register a notification callback."""
        self._listeners.append(fn)

    def _notify(self, event: str, entry: QuarantineEntry) -> None:
        for fn in self._listeners:
            try:
                fn(event, entry)
            except Exception:
                pass  # listeners must not break quarantine logic

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def quarantine(
        self,
        test_name: str,
        *,
        reason: str = "",
        ttl_seconds: float | None = None,
        tags: Sequence[str] = (),
    ) -> QuarantineEntry:
        """Add a test to quarantine."""
        now = time.time()
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        entry = QuarantineEntry(
            test_name=test_name,
            status=QuarantineStatus.ACTIVE,
            reason=reason,
            quarantined_at=now,
            release_after=now + ttl,
            consecutive_passes=0,
            passes_to_release=self._passes_to_release,
            tags=list(tags),
        )
        self._entries[test_name] = entry
        self._save()
        self._notify("quarantined", entry)
        return entry

    def release(self, test_name: str) -> QuarantineEntry | None:
        """Manually release a test from quarantine."""
        entry = self._entries.get(test_name)
        if entry is None:
            return None
        entry.status = QuarantineStatus.RELEASED
        self._save()
        self._notify("released", entry)
        return entry

    def override(self, test_name: str) -> QuarantineEntry | None:
        """Manual override — force a quarantined test to run."""
        entry = self._entries.get(test_name)
        if entry is None:
            return None
        entry.status = QuarantineStatus.MANUAL_OVERRIDE
        self._save()
        self._notify("overridden", entry)
        return entry

    def record_pass(self, test_name: str) -> QuarantineEntry | None:
        """Record a passing run. Auto-releases if threshold met."""
        entry = self._entries.get(test_name)
        if entry is None:
            return None
        entry.consecutive_passes += 1
        if entry.consecutive_passes >= entry.passes_to_release:
            entry.status = QuarantineStatus.RELEASED
            self._notify("auto_released", entry)
        self._save()
        return entry

    def record_fail(self, test_name: str) -> QuarantineEntry | None:
        """Record a failing run. Resets consecutive pass counter."""
        entry = self._entries.get(test_name)
        if entry is None:
            return None
        entry.consecutive_passes = 0
        self._save()
        return entry

    def is_quarantined(self, test_name: str) -> bool:
        """Return True if the test should be skipped."""
        self._expire_stale()
        entry = self._entries.get(test_name)
        if entry is None:
            return False
        return entry.status == QuarantineStatus.ACTIVE

    def get_entry(self, test_name: str) -> QuarantineEntry | None:
        """Get quarantine entry for a test."""
        self._expire_stale()
        return self._entries.get(test_name)

    def summary(self) -> QuarantineSummary:
        """Return quarantine summary."""
        self._expire_stale()
        entries = list(self._entries.values())
        active = sum(1 for e in entries if e.status == QuarantineStatus.ACTIVE)
        released = sum(1 for e in entries if e.status == QuarantineStatus.RELEASED)
        expired = sum(1 for e in entries if e.status == QuarantineStatus.EXPIRED)
        overridden = sum(
            1 for e in entries if e.status == QuarantineStatus.MANUAL_OVERRIDE
        )
        return QuarantineSummary(
            total=len(entries),
            active=active,
            released=released,
            expired=expired,
            overridden=overridden,
            entries=entries,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _expire_stale(self) -> None:
        now = time.time()
        for entry in self._entries.values():
            if (
                entry.status == QuarantineStatus.ACTIVE
                and entry.release_after > 0
                and now > entry.release_after
            ):
                entry.status = QuarantineStatus.EXPIRED
                self._notify("expired", entry)
        self._save()

    def _save(self) -> None:
        if self._store_path is None:
            return
        data = []
        for e in self._entries.values():
            data.append(
                {
                    "test_name": e.test_name,
                    "status": e.status.value,
                    "reason": e.reason,
                    "quarantined_at": e.quarantined_at,
                    "release_after": e.release_after,
                    "consecutive_passes": e.consecutive_passes,
                    "passes_to_release": e.passes_to_release,
                    "tags": e.tags,
                }
            )
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        if self._store_path is None or not self._store_path.exists():
            return
        try:
            data = json.loads(self._store_path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        for item in data:
            entry = QuarantineEntry(
                test_name=item["test_name"],
                status=QuarantineStatus(item.get("status", "active")),
                reason=item.get("reason", ""),
                quarantined_at=item.get("quarantined_at", 0.0),
                release_after=item.get("release_after", 0.0),
                consecutive_passes=item.get("consecutive_passes", 0),
                passes_to_release=item.get("passes_to_release", 3),
                tags=item.get("tags", []),
            )
            self._entries[entry.test_name] = entry
