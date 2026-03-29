"""Conditional hook filter and extended registry (Task 719)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from lidco.hooks.event_bus import HookEvent, HookEventBus


@dataclass
class HookDefinition:
    """Describes a named hook registration."""

    name: str
    event_type: str
    handler: Callable
    if_pattern: str = ""


class ConditionalFilter:
    """Wraps a handler and only calls it when *if_pattern* matches the payload string."""

    def __init__(self, handler: Callable, if_pattern: str = "") -> None:
        self._handler = handler
        self._if_pattern = if_pattern
        self._compiled = re.compile(if_pattern) if if_pattern else None

    def __call__(self, event: HookEvent) -> None:
        if self._compiled is not None:
            payload_str = str(event.payload)
            if not self._compiled.search(payload_str):
                return
        self._handler(event)


class HookRegistry:
    """Extended registry layered on top of :class:`HookEventBus`."""

    def __init__(self, bus: HookEventBus | None = None) -> None:
        self._bus = bus or HookEventBus()
        self._definitions: dict[str, HookDefinition] = {}
        self._wrapped: dict[str, Callable] = {}

    @property
    def bus(self) -> HookEventBus:
        """Return the underlying event bus."""
        return self._bus

    def register(self, defn: HookDefinition) -> None:
        """Register a hook definition; wrap with :class:`ConditionalFilter` if *if_pattern* is set."""
        if defn.name in self._definitions:
            self.unregister(defn.name)
        if defn.if_pattern:
            wrapped: Callable = ConditionalFilter(defn.handler, defn.if_pattern)
        else:
            wrapped = defn.handler
        self._definitions[defn.name] = defn
        self._wrapped[defn.name] = wrapped
        self._bus.subscribe(defn.event_type, wrapped)

    def unregister(self, name: str) -> None:
        """Remove a previously registered hook by name. No-op if not found."""
        defn = self._definitions.pop(name, None)
        wrapped = self._wrapped.pop(name, None)
        if defn is not None and wrapped is not None:
            self._bus.unsubscribe(defn.event_type, wrapped)

    def list_definitions(self) -> list[HookDefinition]:
        """Return all registered definitions."""
        return list(self._definitions.values())

    def emit(self, event: HookEvent) -> int:
        """Forward to ``bus.emit()``. Returns handler count."""
        return self._bus.emit(event)
