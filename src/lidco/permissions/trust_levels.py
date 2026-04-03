"""Trust tiers — auto-escalate based on history, decay over time."""
from __future__ import annotations

import time
from dataclasses import dataclass

TRUST_LEVELS: dict[str, int] = {
    "untrusted": 0,
    "basic": 1,
    "elevated": 2,
    "admin": 3,
}


@dataclass
class TrustEntry:
    """A trust entry for an entity."""

    entity: str
    level: int = 1
    last_activity: float = 0.0
    history_count: int = 0


class TrustManager:
    """Manage trust tiers with auto-escalation and decay."""

    def __init__(
        self,
        decay_seconds: float = 86400.0,
        auto_escalate_threshold: int = 10,
    ) -> None:
        self._decay_seconds = decay_seconds
        self._auto_escalate_threshold = auto_escalate_threshold
        self._entries: dict[str, TrustEntry] = {}

    def set_level(self, entity: str, level: int) -> TrustEntry:
        """Set the trust level for *entity*."""
        entry = self._entries.get(entity)
        if entry is None:
            entry = TrustEntry(
                entity=entity,
                level=level,
                last_activity=time.time(),
            )
            self._entries[entity] = entry
        else:
            entry.level = level
            entry.last_activity = time.time()
        return entry

    def get_level(self, entity: str) -> int:
        """Return the trust level (0 if unknown), applying decay first."""
        entry = self._entries.get(entity)
        if entry is None:
            return 0
        self.apply_decay(entity)
        return entry.level

    def get_entry(self, entity: str) -> TrustEntry | None:
        """Return the TrustEntry or None."""
        return self._entries.get(entity)

    def record_activity(self, entity: str) -> TrustEntry:
        """Record activity; auto-escalate if threshold met."""
        entry = self._entries.get(entity)
        if entry is None:
            entry = TrustEntry(
                entity=entity,
                level=1,
                last_activity=time.time(),
                history_count=1,
            )
            self._entries[entity] = entry
        else:
            entry.history_count += 1
            entry.last_activity = time.time()
            # Auto-escalate if threshold met and below admin
            if (
                entry.history_count >= self._auto_escalate_threshold
                and entry.level < TRUST_LEVELS["admin"]
            ):
                entry.level += 1
                entry.history_count = 0  # Reset counter after escalation
        return entry

    def apply_decay(self, entity: str) -> TrustEntry | None:
        """Decay level by 1 if inactive longer than decay_seconds."""
        entry = self._entries.get(entity)
        if entry is None:
            return None
        now = time.time()
        if now - entry.last_activity > self._decay_seconds and entry.level > 0:
            entry.level -= 1
            entry.last_activity = now
        return entry

    def check_permission(self, entity: str, required_level: int) -> bool:
        """Return True if entity's level >= required_level."""
        return self.get_level(entity) >= required_level

    def all_entries(self) -> list[TrustEntry]:
        """Return all trust entries."""
        return list(self._entries.values())

    def summary(self) -> dict:
        """Return count per level."""
        counts: dict[int, int] = {}
        for entry in self._entries.values():
            counts[entry.level] = counts.get(entry.level, 0) + 1
        return counts
