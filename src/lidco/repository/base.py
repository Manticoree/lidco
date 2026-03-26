"""Repository pattern — generic in-memory repository with query support (stdlib only)."""
from __future__ import annotations

import threading
from dataclasses import asdict
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class EntityNotFoundError(KeyError):
    def __init__(self, entity_id: str, entity_type: str = "Entity") -> None:
        super().__init__(f"{entity_type} {entity_id!r} not found")
        self.entity_id = entity_id
        self.entity_type = entity_type


class Repository(Generic[T]):
    """
    Generic in-memory repository.

    Entities must expose an ``id`` attribute (or string-serializable key).

    Parameters
    ----------
    entity_type:
        Human-readable entity type name for error messages.
    id_attr:
        Name of the identity attribute on entities.
    """

    def __init__(self, entity_type: str = "Entity", id_attr: str = "id") -> None:
        self._entity_type = entity_type
        self._id_attr = id_attr
        self._store: dict[str, T] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------- crud

    def save(self, entity: T) -> T:
        """Insert or update *entity*."""
        eid = str(getattr(entity, self._id_attr))
        with self._lock:
            self._store = {**self._store, eid: entity}
        return entity

    def find_by_id(self, entity_id: str) -> T | None:
        """Return entity or None."""
        with self._lock:
            return self._store.get(str(entity_id))

    def get_by_id(self, entity_id: str) -> T:
        """Return entity.  Raises :exc:`EntityNotFoundError` if missing."""
        entity = self.find_by_id(entity_id)
        if entity is None:
            raise EntityNotFoundError(str(entity_id), self._entity_type)
        return entity

    def delete(self, entity_id: str) -> bool:
        """Remove by id.  Return True if existed."""
        with self._lock:
            if str(entity_id) not in self._store:
                return False
            self._store = {k: v for k, v in self._store.items() if k != str(entity_id)}
        return True

    def exists(self, entity_id: str) -> bool:
        with self._lock:
            return str(entity_id) in self._store

    # ----------------------------------------------------------------- query

    def find_all(self, predicate: Callable[[T], bool] | None = None) -> list[T]:
        """Return all entities, optionally filtered by *predicate*."""
        with self._lock:
            entities = list(self._store.values())
        if predicate is not None:
            entities = [e for e in entities if predicate(e)]
        return entities

    def find_one(self, predicate: Callable[[T], bool]) -> T | None:
        """Return first entity matching *predicate*, or None."""
        with self._lock:
            entities = list(self._store.values())
        for e in entities:
            if predicate(e):
                return e
        return None

    def count(self, predicate: Callable[[T], bool] | None = None) -> int:
        return len(self.find_all(predicate))

    def all_ids(self) -> list[str]:
        with self._lock:
            return sorted(self._store.keys())

    # ----------------------------------------------------------------- helpers

    def clear(self) -> None:
        with self._lock:
            self._store = {}

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def __contains__(self, entity_id: object) -> bool:
        with self._lock:
            return str(entity_id) in self._store
