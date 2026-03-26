"""Entity — base class for domain entities with identity and lifecycle (stdlib only)."""
from __future__ import annotations

import time
import uuid
from typing import Any


class Entity:
    """
    Base class for domain entities.

    Entities have identity (``id``) and lifecycle timestamps.
    Two entities are equal if they have the same type and id.
    """

    def __init__(self, entity_id: str | None = None) -> None:
        self._id = entity_id or str(uuid.uuid4())
        self._created_at = time.time()
        self._updated_at = self._created_at
        self._version = 1

    @property
    def id(self) -> str:
        return self._id

    @property
    def created_at(self) -> float:
        return self._created_at

    @property
    def updated_at(self) -> float:
        return self._updated_at

    @property
    def version(self) -> int:
        return self._version

    def touch(self) -> None:
        """Update the ``updated_at`` timestamp and increment version."""
        self._updated_at = time.time()
        self._version += 1

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return type(self) is type(other) and self._id == other._id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._id))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self._id!r})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self._id,
            "created_at": self._created_at,
            "updated_at": self._updated_at,
            "version": self._version,
        }


class TimestampedEntity(Entity):
    """Entity with soft-delete support."""

    def __init__(self, entity_id: str | None = None) -> None:
        super().__init__(entity_id)
        self._deleted_at: float | None = None

    @property
    def deleted_at(self) -> float | None:
        return self._deleted_at

    @property
    def is_deleted(self) -> bool:
        return self._deleted_at is not None

    def soft_delete(self) -> None:
        """Mark entity as deleted without removing it."""
        self._deleted_at = time.time()
        self.touch()

    def restore(self) -> None:
        """Restore a soft-deleted entity."""
        self._deleted_at = None
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["deleted_at"] = self._deleted_at
        d["is_deleted"] = self.is_deleted
        return d
