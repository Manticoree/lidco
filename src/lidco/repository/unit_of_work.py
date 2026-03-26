"""UnitOfWork — tracks changes and coordinates transactional commit/rollback (stdlib only)."""
from __future__ import annotations

import copy
import threading
from typing import Any


class TransactionError(Exception):
    """Raised when a commit or rollback operation fails."""


class UnitOfWork:
    """
    Tracks new, dirty, and removed entities for transactional persistence.

    Usage::

        uow = UnitOfWork()
        uow.register_new(entity)
        uow.register_dirty(entity)
        uow.commit()   # processes all pending changes
    """

    def __init__(self) -> None:
        self._new: dict[str, Any] = {}
        self._dirty: dict[str, Any] = {}
        self._removed: dict[str, Any] = {}
        self._snapshots: dict[str, Any] = {}
        self._committed: list[dict[str, list]] = []
        self._lock = threading.Lock()
        self._active = False

    # ---------------------------------------------------------------- context

    def __enter__(self) -> "UnitOfWork":
        self.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            self.rollback()
            return False
        self.commit()
        return False

    def begin(self) -> None:
        with self._lock:
            self._active = True
            self._new = {}
            self._dirty = {}
            self._removed = {}

    # -------------------------------------------------------------- registration

    def register_new(self, entity: Any, entity_id: str | None = None) -> None:
        eid = entity_id or str(getattr(entity, "id", id(entity)))
        with self._lock:
            self._new = {**self._new, eid: entity}

    def register_dirty(self, entity: Any, entity_id: str | None = None) -> None:
        eid = entity_id or str(getattr(entity, "id", id(entity)))
        with self._lock:
            if eid not in self._new:
                # Take snapshot before first dirty registration
                if eid not in self._snapshots:
                    try:
                        self._snapshots = {**self._snapshots, eid: copy.deepcopy(entity)}
                    except Exception:
                        pass
                self._dirty = {**self._dirty, eid: entity}

    def register_removed(self, entity: Any, entity_id: str | None = None) -> None:
        eid = entity_id or str(getattr(entity, "id", id(entity)))
        with self._lock:
            self._removed = {**self._removed, eid: entity}
            # Remove from other buckets
            self._new = {k: v for k, v in self._new.items() if k != eid}
            self._dirty = {k: v for k, v in self._dirty.items() if k != eid}

    # --------------------------------------------------------------- commit

    def commit(self) -> dict[str, list]:
        """
        Finalize all changes.

        Returns a summary dict with ``new``, ``dirty``, ``removed`` id lists.
        """
        with self._lock:
            summary = {
                "new": list(self._new.keys()),
                "dirty": list(self._dirty.keys()),
                "removed": list(self._removed.keys()),
            }
            self._committed.append(summary)
            self._new = {}
            self._dirty = {}
            self._removed = {}
            self._snapshots = {}
            self._active = False
        return summary

    def rollback(self) -> None:
        """Discard all pending changes."""
        with self._lock:
            self._new = {}
            self._dirty = {}
            self._removed = {}
            self._snapshots = {}
            self._active = False

    # ---------------------------------------------------------------- state

    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def pending_new(self) -> list[str]:
        with self._lock:
            return list(self._new.keys())

    def pending_dirty(self) -> list[str]:
        with self._lock:
            return list(self._dirty.keys())

    def pending_removed(self) -> list[str]:
        with self._lock:
            return list(self._removed.keys())

    def get_snapshot(self, entity_id: str) -> Any | None:
        with self._lock:
            return self._snapshots.get(entity_id)

    def commit_count(self) -> int:
        with self._lock:
            return len(self._committed)
