"""Q144 — Configuration Migration & Versioning: ConfigBackup."""
from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BackupEntry:
    """A single config backup."""

    id: str
    timestamp: float
    version: str
    data: dict
    label: Optional[str] = None


class ConfigBackup:
    """Manage versioned config backups with a rolling window."""

    def __init__(self, max_backups: int = 20) -> None:
        self._max_backups = max_backups
        self._backups: list[BackupEntry] = []

    def backup(self, data: dict, version: str, label: str | None = None) -> BackupEntry:
        entry = BackupEntry(
            id=uuid.uuid4().hex,
            timestamp=time.time(),
            version=version,
            data=copy.deepcopy(data),
            label=label,
        )
        self._backups.append(entry)
        self.cleanup()
        return entry

    def restore(self, backup_id: str) -> Optional[dict]:
        for entry in self._backups:
            if entry.id == backup_id:
                return copy.deepcopy(entry.data)
        return None

    def list_backups(self) -> list[BackupEntry]:
        """Return backups newest-first."""
        return sorted(self._backups, key=lambda e: e.timestamp, reverse=True)

    def latest(self) -> Optional[BackupEntry]:
        if not self._backups:
            return None
        return max(self._backups, key=lambda e: e.timestamp)

    def delete(self, backup_id: str) -> bool:
        for i, entry in enumerate(self._backups):
            if entry.id == backup_id:
                self._backups.pop(i)
                return True
        return False

    def cleanup(self) -> None:
        """Remove oldest backups beyond *max_backups*."""
        if len(self._backups) > self._max_backups:
            self._backups.sort(key=lambda e: e.timestamp)
            self._backups = self._backups[-self._max_backups:]
