"""Plugin Lifecycle Manager — init, activate, deactivate, uninstall with hot-reload."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol, runtime_checkable


class PluginState(str, Enum):
    """States in the plugin lifecycle."""

    REGISTERED = "registered"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"
    ERROR = "error"
    UNINSTALLED = "uninstalled"


@runtime_checkable
class PluginInterface(Protocol):
    """Protocol that plugins should implement for lifecycle hooks."""

    def on_init(self) -> None: ...
    def on_activate(self) -> None: ...
    def on_deactivate(self) -> None: ...
    def on_uninstall(self) -> None: ...


@dataclass(frozen=True)
class PluginInfo:
    """Immutable snapshot of a managed plugin's state."""

    name: str
    version: str
    state: PluginState
    plugin_instance: Any
    registered_at: float
    last_transition: float
    error_message: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class PluginLifecycleError(Exception):
    """Base error for lifecycle operations."""


class InvalidTransitionError(PluginLifecycleError):
    """Raised when a lifecycle transition is not allowed."""

    def __init__(self, name: str, current: PluginState, target: PluginState) -> None:
        super().__init__(
            f"Plugin {name!r}: cannot transition from {current.value} to {target.value}"
        )
        self.plugin_name = name
        self.current_state = current
        self.target_state = target


class PluginNotRegisteredError(PluginLifecycleError):
    """Raised when operating on an unregistered plugin."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Plugin {name!r} is not registered")
        self.plugin_name = name


# Valid state transitions
_TRANSITIONS: dict[PluginState, set[PluginState]] = {
    PluginState.REGISTERED: {PluginState.INITIALIZED, PluginState.UNINSTALLED, PluginState.ERROR},
    PluginState.INITIALIZED: {PluginState.ACTIVE, PluginState.UNINSTALLED, PluginState.ERROR},
    PluginState.ACTIVE: {PluginState.DEACTIVATED, PluginState.ERROR},
    PluginState.DEACTIVATED: {PluginState.ACTIVE, PluginState.UNINSTALLED, PluginState.ERROR},
    PluginState.ERROR: {PluginState.INITIALIZED, PluginState.UNINSTALLED},
    PluginState.UNINSTALLED: set(),
}


@dataclass
class _ManagedPlugin:
    """Mutable internal record for a managed plugin."""

    name: str
    version: str
    state: PluginState
    instance: Any
    registered_at: float
    last_transition: float
    error_message: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class PluginLifecycleManager:
    """Manages plugin lifecycle transitions: register -> init -> activate -> deactivate -> uninstall.

    Supports hot-reload by deactivating, re-initializing, and reactivating a plugin.
    Lifecycle callbacks on the plugin instance are optional (duck-typed via protocol).
    """

    def __init__(self) -> None:
        self._plugins: dict[str, _ManagedPlugin] = {}
        self._listeners: list[Callable[[str, PluginState, PluginState], None]] = []

    # ------------------------------------------------------------ register

    def register(
        self,
        name: str,
        instance: Any,
        *,
        version: str = "0.0.0",
        metadata: dict[str, str] | None = None,
    ) -> PluginInfo:
        """Register a new plugin instance. Returns its info snapshot."""
        now = time.time()
        managed = _ManagedPlugin(
            name=name,
            version=version,
            state=PluginState.REGISTERED,
            instance=instance,
            registered_at=now,
            last_transition=now,
            metadata=metadata or {},
        )
        self._plugins = {**self._plugins, name: managed}
        return self._snapshot(managed)

    # --------------------------------------------------------- transitions

    def initialize(self, name: str) -> PluginInfo:
        """Transition plugin to INITIALIZED state, calling on_init if available."""
        managed = self._get(name)
        self._check_transition(managed, PluginState.INITIALIZED)
        try:
            if hasattr(managed.instance, "on_init"):
                managed.instance.on_init()
            self._transition(managed, PluginState.INITIALIZED)
        except Exception as exc:
            managed.error_message = str(exc)
            self._transition(managed, PluginState.ERROR)
            raise PluginLifecycleError(f"Init failed for {name!r}: {exc}") from exc
        return self._snapshot(managed)

    def activate(self, name: str) -> PluginInfo:
        """Transition plugin to ACTIVE state, calling on_activate if available."""
        managed = self._get(name)
        self._check_transition(managed, PluginState.ACTIVE)
        try:
            if hasattr(managed.instance, "on_activate"):
                managed.instance.on_activate()
            self._transition(managed, PluginState.ACTIVE)
        except Exception as exc:
            managed.error_message = str(exc)
            self._transition(managed, PluginState.ERROR)
            raise PluginLifecycleError(f"Activate failed for {name!r}: {exc}") from exc
        return self._snapshot(managed)

    def deactivate(self, name: str) -> PluginInfo:
        """Transition plugin to DEACTIVATED state."""
        managed = self._get(name)
        self._check_transition(managed, PluginState.DEACTIVATED)
        try:
            if hasattr(managed.instance, "on_deactivate"):
                managed.instance.on_deactivate()
            self._transition(managed, PluginState.DEACTIVATED)
        except Exception as exc:
            managed.error_message = str(exc)
            self._transition(managed, PluginState.ERROR)
            raise PluginLifecycleError(f"Deactivate failed for {name!r}: {exc}") from exc
        return self._snapshot(managed)

    def uninstall(self, name: str) -> PluginInfo:
        """Transition plugin to UNINSTALLED state and remove from manager."""
        managed = self._get(name)
        self._check_transition(managed, PluginState.UNINSTALLED)
        try:
            if hasattr(managed.instance, "on_uninstall"):
                managed.instance.on_uninstall()
        except Exception:
            pass  # best-effort cleanup
        self._transition(managed, PluginState.UNINSTALLED)
        snapshot = self._snapshot(managed)
        self._plugins = {k: v for k, v in self._plugins.items() if k != name}
        return snapshot

    # ---------------------------------------------------------- hot reload

    def hot_reload(self, name: str, new_instance: Any | None = None) -> PluginInfo:
        """Hot-reload a plugin: deactivate -> reinitialize -> reactivate.

        If *new_instance* is provided the old instance is replaced.
        """
        managed = self._get(name)
        was_active = managed.state == PluginState.ACTIVE

        if was_active:
            self.deactivate(name)

        if new_instance is not None:
            managed.instance = new_instance

        # Reset to REGISTERED so we can re-init
        self._transition(managed, PluginState.REGISTERED)
        self.initialize(name)

        if was_active:
            self.activate(name)

        return self._snapshot(self._get(name))

    # ------------------------------------------------------------ queries

    def get_info(self, name: str) -> PluginInfo:
        return self._snapshot(self._get(name))

    def list_plugins(self) -> list[PluginInfo]:
        return [self._snapshot(m) for m in sorted(self._plugins.values(), key=lambda m: m.name)]

    def list_by_state(self, state: PluginState) -> list[PluginInfo]:
        return [
            self._snapshot(m)
            for m in sorted(self._plugins.values(), key=lambda m: m.name)
            if m.state == state
        ]

    def is_active(self, name: str) -> bool:
        m = self._plugins.get(name)
        return m is not None and m.state == PluginState.ACTIVE

    # ---------------------------------------------------------- listeners

    def add_listener(self, callback: Callable[[str, PluginState, PluginState], None]) -> None:
        """Add a state-transition listener: callback(name, old_state, new_state)."""
        self._listeners = [*self._listeners, callback]

    # ------------------------------------------------------------ helpers

    def _get(self, name: str) -> _ManagedPlugin:
        m = self._plugins.get(name)
        if m is None:
            raise PluginNotRegisteredError(name)
        return m

    def _check_transition(self, managed: _ManagedPlugin, target: PluginState) -> None:
        allowed = _TRANSITIONS.get(managed.state, set())
        if target not in allowed:
            raise InvalidTransitionError(managed.name, managed.state, target)

    def _transition(self, managed: _ManagedPlugin, target: PluginState) -> None:
        old = managed.state
        managed.state = target
        managed.last_transition = time.time()
        for listener in self._listeners:
            try:
                listener(managed.name, old, target)
            except Exception:
                pass

    def _snapshot(self, managed: _ManagedPlugin) -> PluginInfo:
        return PluginInfo(
            name=managed.name,
            version=managed.version,
            state=managed.state,
            plugin_instance=managed.instance,
            registered_at=managed.registered_at,
            last_transition=managed.last_transition,
            error_message=managed.error_message,
            metadata=dict(managed.metadata),
        )

    def __len__(self) -> int:
        return len(self._plugins)

    def __contains__(self, name: object) -> bool:
        return name in self._plugins

    def clear(self) -> None:
        self._plugins = {}
