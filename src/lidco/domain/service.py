"""DomainService — base class and service registry for domain services (stdlib only)."""
from __future__ import annotations

import threading
from typing import Any, Callable


class DomainServiceNotFoundError(KeyError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Domain service {name!r} not registered")
        self.service_name = name


class DomainService:
    """
    Base class for domain services.

    Domain services encapsulate domain logic that doesn't naturally belong
    to a single entity or value object.

    Subclasses should define their own methods and optionally override
    ``service_name`` as a class attribute.
    """

    service_name: str = ""

    def validate(self) -> list[str]:
        """Return a list of validation error messages (empty = valid)."""
        return []

    def is_valid(self) -> bool:
        return len(self.validate()) == 0


class ServiceRegistry:
    """Registry for domain services."""

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}
        self._lock = threading.Lock()

    def register(self, name: str, service: Any) -> None:
        with self._lock:
            self._services = {**self._services, name: service}

    def get(self, name: str) -> Any:
        with self._lock:
            service = self._services.get(name)
        if service is None:
            raise DomainServiceNotFoundError(name)
        return service

    def unregister(self, name: str) -> bool:
        with self._lock:
            if name not in self._services:
                return False
            self._services = {k: v for k, v in self._services.items() if k != name}
        return True

    def list(self) -> list[str]:
        with self._lock:
            return sorted(self._services.keys())

    def __contains__(self, name: object) -> bool:
        with self._lock:
            return name in self._services

    def __len__(self) -> int:
        with self._lock:
            return len(self._services)

    def clear(self) -> None:
        with self._lock:
            self._services = {}
