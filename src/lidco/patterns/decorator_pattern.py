"""Decorator pattern — component wrappers that extend behavior (stdlib only).

Note: this implements the GoF structural Decorator pattern, not Python
function decorators.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Component(ABC):
    """Abstract component interface."""

    @abstractmethod
    def operation(self) -> str:
        """Perform the component's operation."""

    @property
    def description(self) -> str:
        return type(self).__name__


class ConcreteComponent(Component):
    """A basic component implementation."""

    def __init__(self, name: str = "Component") -> None:
        self._name = name

    def operation(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._name


class ComponentDecorator(Component, ABC):
    """Abstract decorator that wraps a :class:`Component`."""

    def __init__(self, component: Component) -> None:
        self._component = component

    @property
    def wrapped(self) -> Component:
        return self._component


class UpperCaseDecorator(ComponentDecorator):
    """Decorator that uppercases the operation result."""

    def operation(self) -> str:
        return self._component.operation().upper()

    @property
    def description(self) -> str:
        return f"UpperCase({self._component.description})"


class PrefixDecorator(ComponentDecorator):
    """Decorator that prepends a prefix to the operation result."""

    def __init__(self, component: Component, prefix: str) -> None:
        super().__init__(component)
        self._prefix = prefix

    def operation(self) -> str:
        return f"{self._prefix}{self._component.operation()}"

    @property
    def description(self) -> str:
        return f"Prefix({self._prefix!r}, {self._component.description})"


class SuffixDecorator(ComponentDecorator):
    """Decorator that appends a suffix to the operation result."""

    def __init__(self, component: Component, suffix: str) -> None:
        super().__init__(component)
        self._suffix = suffix

    def operation(self) -> str:
        return f"{self._component.operation()}{self._suffix}"

    @property
    def description(self) -> str:
        return f"Suffix({self._suffix!r}, {self._component.description})"


class CachingDecorator(ComponentDecorator):
    """Decorator that caches the result of the first call."""

    def __init__(self, component: Component) -> None:
        super().__init__(component)
        self._cached: str | None = None
        self._call_count = 0

    def operation(self) -> str:
        if self._cached is None:
            self._cached = self._component.operation()
        self._call_count += 1
        return self._cached

    @property
    def call_count(self) -> int:
        return self._call_count

    def invalidate(self) -> None:
        """Clear the cache."""
        self._cached = None

    @property
    def description(self) -> str:
        return f"Caching({self._component.description})"


class LoggingDecorator(ComponentDecorator):
    """Decorator that logs all operation calls."""

    def __init__(self, component: Component) -> None:
        super().__init__(component)
        self._log: list[str] = []

    def operation(self) -> str:
        result = self._component.operation()
        self._log.append(result)
        return result

    @property
    def log(self) -> list[str]:
        return list(self._log)

    @property
    def description(self) -> str:
        return f"Logging({self._component.description})"
