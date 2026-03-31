"""
Team Template Registry — shared template repository with versioning,
import/export, and conflict resolution.

Stdlib only — no external dependencies.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RegistryError(Exception):
    """Raised on registry errors."""


class ConflictError(RegistryError):
    """Raised when a version conflict is detected."""


class TemplateNotFoundError(RegistryError):
    """Raised when a template is not found in the registry."""


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class ConflictStrategy(Enum):
    """Strategy for resolving import conflicts."""
    OVERWRITE = "overwrite"
    SKIP = "skip"
    RENAME = "rename"
    ERROR = "error"


@dataclass(frozen=True)
class TemplateEntry:
    """A versioned template entry in the registry."""

    name: str
    data: dict[str, Any]
    version: str = "1.0"
    author: str = ""
    updated_at: float = 0.0
    checksum: str = ""

    def with_version(self, version: str) -> "TemplateEntry":
        """Return a new entry with updated version."""
        return TemplateEntry(
            name=self.name,
            data=self.data,
            version=version,
            author=self.author,
            updated_at=time.time(),
            checksum=self.checksum,
        )


@dataclass(frozen=True)
class ImportResult:
    """Result of an import operation."""

    imported: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Checksum utility
# ---------------------------------------------------------------------------

def _compute_checksum(data: dict[str, Any]) -> str:
    """Compute a simple checksum for conflict detection."""
    import hashlib
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Team Template Registry
# ---------------------------------------------------------------------------

class TeamTemplateRegistry:
    """Shared template registry with versioning and conflict resolution."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self._entries: dict[str, TemplateEntry] = {}
        self._history: dict[str, list[TemplateEntry]] = {}
        self._storage_dir = Path(storage_dir) if storage_dir else None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(
        self,
        name: str,
        data: dict[str, Any],
        version: str = "1.0",
        author: str = "",
    ) -> TemplateEntry:
        """Add or update a template in the registry."""
        checksum = _compute_checksum(data)
        entry = TemplateEntry(
            name=name,
            data=data,
            version=version,
            author=author,
            updated_at=time.time(),
            checksum=checksum,
        )
        # Save history
        if name in self._entries:
            if name not in self._history:
                self._history[name] = []
            self._history[name].append(self._entries[name])
        self._entries[name] = entry
        return entry

    def get(self, name: str) -> TemplateEntry | None:
        """Get a template entry by name."""
        return self._entries.get(name)

    def remove(self, name: str) -> bool:
        """Remove a template. Returns True if found."""
        removed = self._entries.pop(name, None)
        if removed is not None:
            self._history.pop(name, None)
            return True
        return False

    def list_entries(self) -> list[TemplateEntry]:
        """List all template entries."""
        return list(self._entries.values())

    def search(self, query: str) -> list[TemplateEntry]:
        """Search entries by name substring."""
        query_lower = query.lower()
        return [
            e for e in self._entries.values()
            if query_lower in e.name.lower()
        ]

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------

    def get_history(self, name: str) -> list[TemplateEntry]:
        """Get version history for a template."""
        return list(self._history.get(name, []))

    def get_version(self, name: str, version: str) -> TemplateEntry | None:
        """Get a specific version of a template."""
        current = self._entries.get(name)
        if current and current.version == version:
            return current
        for entry in self._history.get(name, []):
            if entry.version == version:
                return entry
        return None

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def export_all(self) -> dict[str, Any]:
        """Export all entries as a dict."""
        return {
            "entries": [
                {
                    "name": e.name,
                    "data": e.data,
                    "version": e.version,
                    "author": e.author,
                    "updated_at": e.updated_at,
                    "checksum": e.checksum,
                }
                for e in self._entries.values()
            ],
        }

    def export_entry(self, name: str) -> dict[str, Any] | None:
        """Export a single entry as a dict."""
        entry = self._entries.get(name)
        if entry is None:
            return None
        return {
            "name": entry.name,
            "data": entry.data,
            "version": entry.version,
            "author": entry.author,
            "updated_at": entry.updated_at,
            "checksum": entry.checksum,
        }

    def import_entries(
        self,
        data: dict[str, Any],
        strategy: ConflictStrategy = ConflictStrategy.SKIP,
    ) -> ImportResult:
        """Import entries from exported data with conflict resolution."""
        entries = data.get("entries", [])
        imported: list[str] = []
        skipped: list[str] = []
        conflicts: list[str] = []
        errors: list[str] = []

        for raw in entries:
            name = raw.get("name", "")
            if not name:
                errors.append("Entry missing name")
                continue

            entry_data = raw.get("data", {})
            version = raw.get("version", "1.0")
            author = raw.get("author", "")

            existing = self._entries.get(name)
            if existing is not None:
                new_checksum = _compute_checksum(entry_data)
                if existing.checksum == new_checksum:
                    skipped.append(name)
                    continue

                # Conflict
                if strategy == ConflictStrategy.ERROR:
                    conflicts.append(name)
                    continue
                elif strategy == ConflictStrategy.SKIP:
                    skipped.append(name)
                    continue
                elif strategy == ConflictStrategy.RENAME:
                    new_name = f"{name}_imported"
                    counter = 1
                    while new_name in self._entries:
                        counter += 1
                        new_name = f"{name}_imported_{counter}"
                    self.add(new_name, entry_data, version, author)
                    imported.append(new_name)
                    conflicts.append(name)
                    continue
                # OVERWRITE falls through

            self.add(name, entry_data, version, author)
            imported.append(name)

        return ImportResult(
            imported=tuple(imported),
            skipped=tuple(skipped),
            conflicts=tuple(conflicts),
            errors=tuple(errors),
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path | None = None) -> str:
        """Save registry to a JSON file. Returns the path."""
        target = Path(path) if path else (
            self._storage_dir / "team_templates.json" if self._storage_dir else None
        )
        if target is None:
            raise RegistryError("No storage path configured")
        target.parent.mkdir(parents=True, exist_ok=True)
        data = self.export_all()
        target.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return str(target)

    def load(self, path: str | Path | None = None) -> int:
        """Load registry from a JSON file. Returns count loaded."""
        target = Path(path) if path else (
            self._storage_dir / "team_templates.json" if self._storage_dir else None
        )
        if target is None or not target.exists():
            return 0
        raw = json.loads(target.read_text(encoding="utf-8"))
        result = self.import_entries(raw, strategy=ConflictStrategy.OVERWRITE)
        return len(result.imported)

    @property
    def count(self) -> int:
        """Number of entries in the registry."""
        return len(self._entries)
