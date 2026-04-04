"""EventRouter2 — pattern-based event routing with priority dispatch (stdlib only)."""
from __future__ import annotations

import fnmatch
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class RouteEntry:
    id: str
    pattern: str
    handler: Callable[..., Any]
    priority: int = 0


@dataclass
class RoutedEvent:
    type: str
    data: dict
    id: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


class EventRouter2:
    """
    Route events to handlers based on glob patterns.

    Avoids name collision with ``lidco.webhooks.router`` vs
    ``lidco.events.bus.EventBus``.
    """

    def __init__(self) -> None:
        self._routes: List[RouteEntry] = []

    # -------------------------------------------------------- add_route

    def add_route(
        self, pattern: str, handler: Callable[..., Any], priority: int = 0
    ) -> str:
        """Register *handler* for events whose ``type`` matches *pattern* (glob).

        Returns route ID.
        """
        route_id = uuid.uuid4().hex
        entry = RouteEntry(id=route_id, pattern=pattern, handler=handler, priority=priority)
        self._routes.append(entry)
        return route_id

    def remove_route(self, route_id: str) -> bool:
        """Remove route by ID. Return True if found."""
        before = len(self._routes)
        self._routes = [r for r in self._routes if r.id != route_id]
        return len(self._routes) < before

    # -------------------------------------------------------- route

    def route(self, event: RoutedEvent) -> list:
        """Route *event* to all matching handlers (sorted by priority desc).

        Returns list of handler results.
        """
        matching = [
            r for r in self._routes if fnmatch.fnmatch(event.type, r.pattern)
        ]
        matching.sort(key=lambda r: r.priority, reverse=True)
        results: list = []
        for entry in matching:
            try:
                result = entry.handler(event)
                results.append(result)
            except Exception as exc:
                results.append({"error": str(exc)})
        return results

    # -------------------------------------------------------- filter_chain

    @staticmethod
    def filter_chain(event: RoutedEvent, filters: List[Callable[[RoutedEvent], bool]]) -> bool:
        """Run *event* through a chain of filter functions.

        Returns True only if ALL filters return True.
        """
        return all(f(event) for f in filters)

    # -------------------------------------------------------- priority_dispatch

    def priority_dispatch(self, events: List[RoutedEvent]) -> list:
        """Dispatch multiple events, each routed independently.

        Returns flat list of all handler results.
        """
        results: list = []
        for ev in events:
            results.extend(self.route(ev))
        return results
