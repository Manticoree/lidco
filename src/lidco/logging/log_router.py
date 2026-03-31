"""Route log records to multiple handlers with level and filter support."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from lidco.logging.structured_logger import LogRecord, LEVEL_ORDER


@dataclass
class Route:
    """A named routing destination."""

    name: str
    handler: Callable[[LogRecord], None]
    min_level: str = "debug"
    filter_fn: Optional[Callable[[LogRecord], bool]] = None
    enabled: bool = field(default=True, repr=False)


class LogRouter:
    """Fan-out log records to registered routes."""

    def __init__(self) -> None:
        self._routes: dict[str, Route] = {}
        self._routed_count: int = 0

    # -- properties ----------------------------------------------------------

    @property
    def routed_count(self) -> int:
        return self._routed_count

    # -- public API ----------------------------------------------------------

    def add_route(
        self,
        name: str,
        handler: Callable[[LogRecord], None],
        min_level: str = "debug",
        filter_fn: Optional[Callable[[LogRecord], bool]] = None,
    ) -> Route:
        route = Route(name=name, handler=handler, min_level=min_level, filter_fn=filter_fn)
        self._routes[name] = route
        return route

    def remove_route(self, name: str) -> bool:
        return self._routes.pop(name, None) is not None

    def route(self, record: LogRecord) -> None:
        """Send *record* to all matching, enabled routes."""
        rec_level = LEVEL_ORDER.get(record.level, 0)
        for r in self._routes.values():
            if not r.enabled:
                continue
            if rec_level < LEVEL_ORDER.get(r.min_level, 0):
                continue
            if r.filter_fn is not None and not r.filter_fn(record):
                continue
            r.handler(record)
            self._routed_count += 1

    def list_routes(self) -> list[Route]:
        return list(self._routes.values())

    def enable(self, name: str) -> None:
        if name in self._routes:
            self._routes[name].enabled = True

    def disable(self, name: str) -> None:
        if name in self._routes:
            self._routes[name].enabled = False
