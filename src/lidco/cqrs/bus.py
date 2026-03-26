"""CQRS command/query bus with in-process handlers (stdlib only)."""
from __future__ import annotations

import inspect
import threading
from dataclasses import dataclass
from typing import Any, Callable


class CommandNotRegisteredError(KeyError):
    def __init__(self, name: str) -> None:
        super().__init__(f"No handler registered for command {name!r}")
        self.command_name = name


class QueryNotRegisteredError(KeyError):
    def __init__(self, name: str) -> None:
        super().__init__(f"No handler registered for query {name!r}")
        self.query_name = name


@dataclass
class CommandResult:
    success: bool
    data: Any = None
    error: str = ""


class CommandBus:
    """
    Synchronous in-process command bus.

    A command handler is registered by command class name (or explicit name).
    Each command type maps to exactly ONE handler.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable] = {}
        self._middleware: list[Callable] = []
        self._lock = threading.Lock()

    def register(self, handler: Callable, name: str | None = None) -> None:
        """Register *handler* for command *name* (default: handler's class/function name)."""
        key = name or getattr(handler, "__name__", None) or str(handler)
        with self._lock:
            self._handlers = {**self._handlers, key: handler}

    def unregister(self, name: str) -> bool:
        with self._lock:
            if name not in self._handlers:
                return False
            self._handlers = {k: v for k, v in self._handlers.items() if k != name}
        return True

    def use(self, middleware: Callable) -> None:
        """Add a middleware callable: ``middleware(command, next_fn) -> Any``."""
        self._middleware = [*self._middleware, middleware]

    def dispatch(self, command: Any, name: str | None = None) -> CommandResult:
        """
        Dispatch *command* through middleware to its handler.

        The command name is resolved as:
        1. Explicit *name* argument
        2. ``command.__class__.__name__``
        """
        key = name or command.__class__.__name__
        with self._lock:
            handler = self._handlers.get(key)
        if handler is None:
            raise CommandNotRegisteredError(key)

        def _call() -> Any:
            return handler(command)

        # Walk middleware chain
        fn = _call
        for mw in reversed(self._middleware):
            _prev = fn
            def _make_next(mw=mw, prev=_prev):
                def _next():
                    return mw(command, prev)
                return _next
            fn = _make_next()

        try:
            result = fn()
            return CommandResult(success=True, data=result)
        except Exception as exc:
            return CommandResult(success=False, error=str(exc))

    def registered_commands(self) -> list[str]:
        with self._lock:
            return sorted(self._handlers.keys())


class QueryBus:
    """
    Synchronous in-process query bus.

    Unlike commands, queries are read-only and may have multiple projections,
    but each query name maps to exactly ONE handler.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable] = {}
        self._lock = threading.Lock()

    def register(self, handler: Callable, name: str | None = None) -> None:
        key = name or getattr(handler, "__name__", None) or str(handler)
        with self._lock:
            self._handlers = {**self._handlers, key: handler}

    def unregister(self, name: str) -> bool:
        with self._lock:
            if name not in self._handlers:
                return False
            self._handlers = {k: v for k, v in self._handlers.items() if k != name}
        return True

    def query(self, q: Any, name: str | None = None) -> Any:
        """Execute a query.  Raises :exc:`QueryNotRegisteredError` if no handler."""
        key = name or q.__class__.__name__
        with self._lock:
            handler = self._handlers.get(key)
        if handler is None:
            raise QueryNotRegisteredError(key)
        return handler(q)

    def registered_queries(self) -> list[str]:
        with self._lock:
            return sorted(self._handlers.keys())
