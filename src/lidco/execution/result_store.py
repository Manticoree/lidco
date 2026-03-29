"""Q124 — ResultStore: store task results with optional TTL."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class StoredResult:
    id: str
    key: str
    value: Any
    created_at: float
    ttl: Optional[float] = None  # seconds

    @property
    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl


class ResultStore:
    def __init__(self) -> None:
        self._store: dict[str, StoredResult] = {}

    def put(self, key: str, value: Any, ttl: Optional[float] = None) -> StoredResult:
        entry = StoredResult(
            id=str(uuid.uuid4()),
            key=key,
            value=value,
            created_at=time.time(),
            ttl=ttl,
        )
        self._store[key] = entry
        return entry

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.is_expired:
            del self._store[key]
            return None
        return entry.value

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def keys(self) -> list[str]:
        return list(self._store.keys())

    def clear_expired(self) -> int:
        expired = [k for k, v in self._store.items() if v.is_expired]
        for k in expired:
            del self._store[k]
        return len(expired)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
