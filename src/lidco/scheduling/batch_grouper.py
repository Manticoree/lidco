"""BatchGrouper — group items into batches by key with size/time limits (stdlib only)."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Batch:
    """A completed batch of items."""

    id: str
    group_key: str
    items: list[Any]
    created_at: float


class BatchGrouper:
    """Accumulate items by group key; emit batches when full or timed-out."""

    def __init__(self, max_batch_size: int = 10, max_wait_seconds: float = 60.0) -> None:
        self._max_batch_size = max_batch_size
        self._max_wait_seconds = max_wait_seconds
        self._pending: dict[str, list[Any]] = {}
        self._first_add: dict[str, float] = {}
        self._batches_created: int = 0
        self._items_processed: int = 0

    def add(self, item: Any, group_key: str = "default") -> Optional[Batch]:
        """Add an item. Return a *Batch* if the group is full or time-expired."""
        now = time.time()

        if group_key not in self._pending:
            self._pending = {**self._pending, group_key: []}
            self._first_add = {**self._first_add, group_key: now}

        self._pending[group_key] = [*self._pending[group_key], item]

        # check size trigger
        if len(self._pending[group_key]) >= self._max_batch_size:
            return self._emit(group_key)

        # check time trigger
        elapsed = now - self._first_add.get(group_key, now)
        if elapsed >= self._max_wait_seconds:
            return self._emit(group_key)

        return None

    def flush(self, group_key: str | None = None) -> list[Batch]:
        """Force-flush pending items. If *group_key* is None, flush all."""
        batches: list[Batch] = []
        keys = [group_key] if group_key is not None else list(self._pending.keys())
        for key in keys:
            if key in self._pending and self._pending[key]:
                batches.append(self._emit(key))
        return batches

    def pending_count(self, group_key: str | None = None) -> int:
        """Count of pending items, optionally for a specific group."""
        if group_key is not None:
            return len(self._pending.get(group_key, []))
        return sum(len(v) for v in self._pending.values())

    def stats(self) -> dict:
        """Return batching statistics."""
        return {
            "batches_created": self._batches_created,
            "items_processed": self._items_processed,
            "groups": list(self._pending.keys()),
        }

    # ---------------------------------------------------------------- private

    def _emit(self, group_key: str) -> Batch:
        items = self._pending.pop(group_key, [])
        self._first_add.pop(group_key, None)
        batch = Batch(
            id=uuid.uuid4().hex,
            group_key=group_key,
            items=items,
            created_at=time.time(),
        )
        self._batches_created += 1
        self._items_processed += len(items)
        return batch
