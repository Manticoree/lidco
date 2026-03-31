"""Reconcile agent context when files change externally."""
from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass
class CachedFile:
    file_path: str
    content: str
    mtime: float
    read_at: float = field(default_factory=time.time)


@dataclass
class ReconciliationAction:
    file_path: str
    action: str  # "update", "warn_conflict", "remove"
    reason: str
    old_mtime: float | None = None
    new_mtime: float | None = None


@dataclass
class ReconciliationResult:
    actions: list[ReconciliationAction]
    conflicts: list[str]
    updated: list[str]
    removed: list[str]


class ContextReconciler:
    def __init__(self):
        self._cache: dict[str, CachedFile] = {}
        self._editing: set[str] = set()  # files currently being edited by agent

    def cache_file(self, file_path: str, content: str, mtime: float) -> None:
        """Cache a file's content and mtime after agent reads it."""
        self._cache = {
            **self._cache,
            file_path: CachedFile(file_path=file_path, content=content, mtime=mtime),
        }

    def mark_editing(self, file_path: str) -> None:
        """Mark a file as currently being edited by the agent."""
        self._editing = {*self._editing, file_path}

    def unmark_editing(self, file_path: str) -> None:
        """Unmark a file from editing."""
        self._editing = self._editing - {file_path}

    def get_cached(self, file_path: str) -> CachedFile | None:
        return self._cache.get(file_path)

    @property
    def editing_files(self) -> set[str]:
        return set(self._editing)

    def reconcile(self, changes: list) -> ReconciliationResult:
        """Process file changes and determine actions needed.

        changes: list of objects with file_path, change_type, new_mtime attributes.
        """
        actions: list[ReconciliationAction] = []
        conflicts: list[str] = []
        updated: list[str] = []
        removed: list[str] = []

        for change in changes:
            file_path = change.file_path
            change_type = change.change_type

            if change_type == "deleted":
                if file_path in self._cache:
                    actions.append(ReconciliationAction(
                        file_path=file_path, action="remove",
                        reason="File deleted externally",
                        old_mtime=self._cache[file_path].mtime,
                    ))
                    removed.append(file_path)
                    # Remove from cache
                    new_cache = dict(self._cache)
                    new_cache.pop(file_path, None)
                    self._cache = new_cache
                continue

            if change_type in ("modified", "created"):
                if file_path in self._editing:
                    # Conflict: agent is editing this file
                    cached = self._cache.get(file_path)
                    old_mt = cached.mtime if cached else 0
                    actions.append(ReconciliationAction(
                        file_path=file_path, action="warn_conflict",
                        reason="File modified externally while agent is editing",
                        old_mtime=old_mt,
                        new_mtime=getattr(change, "new_mtime", None),
                    ))
                    conflicts.append(file_path)
                elif file_path in self._cache:
                    actions.append(ReconciliationAction(
                        file_path=file_path, action="update",
                        reason="File modified externally, context needs refresh",
                        old_mtime=self._cache[file_path].mtime,
                        new_mtime=getattr(change, "new_mtime", None),
                    ))
                    updated.append(file_path)

        return ReconciliationResult(
            actions=actions, conflicts=conflicts,
            updated=updated, removed=removed,
        )

    def clear_cache(self) -> None:
        """Clear all cached files."""
        self._cache = {}
        self._editing = set()
