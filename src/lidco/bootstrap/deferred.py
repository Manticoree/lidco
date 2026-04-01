"""Lazy module initialization with dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class DeferredModule:
    """A lazily initialized module."""

    name: str
    factory: Callable[..., Any]
    depends_on: tuple[str, ...] = ()
    initialized: bool = False


class CircularDependencyError(Exception):
    """Raised when circular dependency detected."""


class ModuleNotRegisteredError(Exception):
    """Raised when resolving an unregistered module."""


class DeferredInitializer:
    """Lazily initializes modules, resolving dependencies first."""

    def __init__(self) -> None:
        self._modules: dict[str, DeferredModule] = {}
        self._instances: dict[str, Any] = {}

    def register(
        self,
        name: str,
        factory: Callable[..., Any],
        depends_on: tuple[str, ...] = (),
    ) -> None:
        """Register a deferred module."""
        self._modules[name] = DeferredModule(
            name=name, factory=factory, depends_on=depends_on,
        )

    def resolve(self, name: str) -> Any:
        """Lazily initialize and return the module, resolving deps first."""
        if name not in self._modules:
            raise ModuleNotRegisteredError(f"Module '{name}' is not registered.")
        if name in self._instances:
            return self._instances[name]
        return self._resolve_with_chain(name, set())

    def is_initialized(self, name: str) -> bool:
        """Check whether a module has been initialized."""
        return name in self._instances

    def list_modules(self) -> list[str]:
        """Return all registered module names."""
        return list(self._modules.keys())

    def list_initialized(self) -> list[str]:
        """Return names of initialized modules."""
        return [n for n in self._modules if n in self._instances]

    def has_circular(self) -> bool:
        """Detect circular dependencies across all modules."""
        for name in self._modules:
            if self._detect_cycle(name, set()):
                return True
        return False

    def reset(self, name: str | None = None) -> None:
        """Reset one or all modules back to uninitialized."""
        if name is not None:
            self._instances.pop(name, None)
            if name in self._modules:
                mod = self._modules[name]
                self._modules[name] = DeferredModule(
                    name=mod.name,
                    factory=mod.factory,
                    depends_on=mod.depends_on,
                    initialized=False,
                )
        else:
            self._instances.clear()
            for n, mod in list(self._modules.items()):
                self._modules[n] = DeferredModule(
                    name=mod.name,
                    factory=mod.factory,
                    depends_on=mod.depends_on,
                    initialized=False,
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_with_chain(self, name: str, visiting: set[str]) -> Any:
        if name in self._instances:
            return self._instances[name]
        if name in visiting:
            raise CircularDependencyError(
                f"Circular dependency detected involving '{name}'."
            )
        if name not in self._modules:
            raise ModuleNotRegisteredError(f"Module '{name}' is not registered.")

        visiting = visiting | {name}
        mod = self._modules[name]

        # Resolve dependencies first
        for dep in mod.depends_on:
            self._resolve_with_chain(dep, visiting)

        instance = mod.factory()
        self._instances[name] = instance
        self._modules[name] = DeferredModule(
            name=mod.name,
            factory=mod.factory,
            depends_on=mod.depends_on,
            initialized=True,
        )
        return instance

    def _detect_cycle(self, name: str, visiting: set[str]) -> bool:
        if name in visiting:
            return True
        if name not in self._modules:
            return False
        visiting = visiting | {name}
        for dep in self._modules[name].depends_on:
            if self._detect_cycle(dep, visiting):
                return True
        return False
