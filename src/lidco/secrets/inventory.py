"""SecretInventory — track secrets, age, rotation status, and risk."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class SecretEntry:
    """An entry in the secret inventory."""

    name: str
    provider: str = "unknown"
    created_at: float = 0.0
    last_rotated: float | None = None
    rotation_interval_days: int = 90
    exposure_risk: str = "low"  # low / medium / high / critical
    tags: list[str] = field(default_factory=list)


_VALID_RISKS = {"low", "medium", "high", "critical"}


class SecretInventory:
    """Track all known secrets and their rotation/risk status."""

    def __init__(self) -> None:
        self._entries: dict[str, SecretEntry] = {}

    def add(self, entry: SecretEntry) -> SecretEntry:
        """Add or overwrite a secret entry."""
        if not entry.created_at:
            entry.created_at = time.time()
        self._entries[entry.name] = entry
        return entry

    def get(self, name: str) -> SecretEntry | None:
        """Look up an entry by name."""
        return self._entries.get(name)

    def remove(self, name: str) -> bool:
        """Remove an entry.  Returns True if it existed."""
        if name in self._entries:
            del self._entries[name]
            return True
        return False

    def stale(self, threshold_days: int = 90) -> list[SecretEntry]:
        """Return entries not rotated within *threshold_days*."""
        now = time.time()
        cutoff = now - threshold_days * 86400
        result: list[SecretEntry] = []
        for entry in self._entries.values():
            rotated = entry.last_rotated if entry.last_rotated is not None else entry.created_at
            if rotated < cutoff:
                result.append(entry)
        return result

    def by_risk(self, risk: str) -> list[SecretEntry]:
        """Return entries matching *risk* level."""
        return [e for e in self._entries.values() if e.exposure_risk == risk]

    def mark_rotated(self, name: str) -> SecretEntry | None:
        """Update *last_rotated* to now.  Returns None if not found."""
        entry = self._entries.get(name)
        if entry is None:
            return None
        entry.last_rotated = time.time()
        return entry

    def all_entries(self) -> list[SecretEntry]:
        """Return all entries."""
        return list(self._entries.values())

    def summary(self) -> dict:
        """Return inventory statistics."""
        by_risk: dict[str, int] = {}
        for entry in self._entries.values():
            by_risk[entry.exposure_risk] = by_risk.get(entry.exposure_risk, 0) + 1
        return {
            "total": len(self._entries),
            "by_risk": by_risk,
            "stale": len(self.stale()),
        }
