"""Dependency injection container (stdlib only)."""
from __future__ import annotations

import functools
import inspect
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class CircularDependencyError(Exception):
    """Raised when resolving a service creates a circular dependency chain."""

    def __init__(self, chain: list[str]) -> None:
        self.chain = chain
        super().__init__(f"Circular dependency detected: {' -> '.join(chain)}")


@dataclass
class _Registration:
    factory: Any          # callable factory or raw value
    singleton: bool
    is_value: bool        # True if registered as a plain value


class Container:
    """
    Lightweight dependency injection container.

    Example::

        c = Container()
        c.register("config", {"debug": True})
        c.register("logger", lambda: Logger(), singleton=True)
        logger = c.resolve("logger")
    """

    def __init__(self) -> None:
        self._registrations: dict[str, _Registration] = {}
        self._singletons: dict[str, Any] = {}
        self._resolving: set[str] = set()

    # ----------------------------------------------------------------- register

    def register(
        self,
        name: str,
        factory_or_value: Any,
        singleton: bool = True,
    ) -> None:
        """
        Register a service.

        If *factory_or_value* is callable it is treated as a factory;
        otherwise it is stored as a plain value (always behaves as singleton).
        """
        is_value = not callable(factory_or_value)
        self._registrations = {
            **self._registrations,
            name: _Registration(
                factory=factory_or_value,
                singleton=singleton or is_value,
                is_value=is_value,
            ),
        }
        # Clear cached singleton if re-registering
        self._singletons.pop(name, None)

    # ------------------------------------------------------------------ resolve

    def resolve(self, name: str) -> Any:
        """
        Resolve a service by name.

        Raises
        ------
        KeyError
            If *name* is not registered.
        CircularDependencyError
            If a circular dependency is detected.
        """
        if name not in self._registrations:
            raise KeyError(f"Service {name!r} is not registered")

        reg = self._registrations[name]

        if reg.is_value:
            return reg.factory

        if reg.singleton and name in self._singletons:
            return self._singletons[name]

        if name in self._resolving:
            chain = sorted(self._resolving) + [name]
            raise CircularDependencyError(chain)

        self._resolving.add(name)
        try:
            instance = self._call_factory(reg.factory)
        finally:
            self._resolving.discard(name)

        if reg.singleton:
            self._singletons[name] = instance

        return instance

    def _call_factory(self, factory: Callable) -> Any:
        """Call *factory*, auto-resolving parameters from the container."""
        try:
            sig = inspect.signature(factory)
        except (ValueError, TypeError):
            return factory()

        kwargs: dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            if param.default is not inspect.Parameter.empty:
                continue
            if self.is_registered(param_name):
                kwargs[param_name] = self.resolve(param_name)

        return factory(**kwargs)

    # ------------------------------------------------------------------ inject

    def inject(self, fn: Callable[..., T]) -> Callable[..., T]:
        """
        Decorator that auto-resolves unbound parameters from the container.

        Explicit keyword arguments at call time override container resolution.
        """
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                sig = inspect.signature(fn)
            except (ValueError, TypeError):
                return fn(*args, **kwargs)

            bound_names = set()
            try:
                bound = sig.bind_partial(*args, **kwargs)
                bound_names = set(bound.arguments.keys())
            except TypeError:
                pass

            extra: dict[str, Any] = {}
            for param_name, param in sig.parameters.items():
                if param.kind in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                ):
                    continue
                if param_name in bound_names or param_name in kwargs:
                    continue
                if self.is_registered(param_name):
                    extra[param_name] = self.resolve(param_name)

            return fn(*args, **{**extra, **kwargs})

        return wrapper  # type: ignore[return-value]

    # ----------------------------------------------------------------- helpers

    def is_registered(self, name: str) -> bool:
        return name in self._registrations

    def names(self) -> list[str]:
        return sorted(self._registrations.keys())

    def clear(self) -> None:
        self._registrations = {}
        self._singletons = {}
        self._resolving = set()
