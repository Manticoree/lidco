"""Extension Point Registry — named extension points with type-safe hooks and priority."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class HookPriority(int, Enum):
    """Priority levels for hook execution order (lower runs first)."""

    HIGHEST = 0
    HIGH = 25
    NORMAL = 50
    LOW = 75
    LOWEST = 100


@dataclass(frozen=True)
class HookRegistration:
    """Immutable record of a registered hook."""

    name: str
    callback: Callable[..., Any]
    priority: HookPriority
    is_async: bool
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtensionPoint:
    """Defines a named extension point that hooks can attach to."""

    name: str
    description: str = ""
    param_types: tuple[str, ...] = ()
    return_type: str = "Any"


class ExtensionPointError(Exception):
    """Raised for extension point related errors."""


class DuplicateExtensionPointError(ExtensionPointError):
    """Raised when registering an extension point with a name that already exists."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Extension point {name!r} already registered")
        self.point_name = name


class ExtensionPointNotFoundError(ExtensionPointError):
    """Raised when referencing a non-existent extension point."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Extension point {name!r} not found")
        self.point_name = name


class ExtensionPointRegistry:
    """Registry for named extension points with prioritised hook execution.

    Extension points are named slots that plugins can attach hooks to.
    Hooks run in priority order (lowest number first). Both sync and async
    hooks are supported.
    """

    def __init__(self) -> None:
        self._points: dict[str, ExtensionPoint] = {}
        self._hooks: dict[str, list[HookRegistration]] = {}

    # ---------------------------------------------------------------- points

    def define(
        self,
        name: str,
        description: str = "",
        param_types: tuple[str, ...] = (),
        return_type: str = "Any",
    ) -> ExtensionPoint:
        """Define a new extension point. Raises if already exists."""
        if name in self._points:
            raise DuplicateExtensionPointError(name)
        point = ExtensionPoint(
            name=name,
            description=description,
            param_types=param_types,
            return_type=return_type,
        )
        self._points = {**self._points, name: point}
        self._hooks = {**self._hooks, name: []}
        return point

    def get_point(self, name: str) -> ExtensionPoint:
        """Return the extension point definition. Raises if not found."""
        if name not in self._points:
            raise ExtensionPointNotFoundError(name)
        return self._points[name]

    def list_points(self) -> list[ExtensionPoint]:
        """Return all defined extension points sorted by name."""
        return [self._points[k] for k in sorted(self._points)]

    def remove_point(self, name: str) -> bool:
        """Remove an extension point and all its hooks. Returns True if existed."""
        if name not in self._points:
            return False
        self._points = {k: v for k, v in self._points.items() if k != name}
        self._hooks = {k: v for k, v in self._hooks.items() if k != name}
        return True

    # ----------------------------------------------------------------- hooks

    def add_hook(
        self,
        point_name: str,
        callback: Callable[..., Any],
        *,
        priority: HookPriority = HookPriority.NORMAL,
        name: str = "",
        metadata: dict[str, str] | None = None,
    ) -> HookRegistration:
        """Attach a hook to an extension point.

        Hooks are sorted by priority (ascending) on insertion.
        """
        if point_name not in self._points:
            raise ExtensionPointNotFoundError(point_name)

        hook_name = name or getattr(callback, "__name__", "anonymous")
        is_async = inspect.iscoroutinefunction(callback)
        reg = HookRegistration(
            name=hook_name,
            callback=callback,
            priority=priority,
            is_async=is_async,
            metadata=metadata or {},
        )
        hooks = [*self._hooks.get(point_name, []), reg]
        hooks.sort(key=lambda h: h.priority.value)
        self._hooks = {**self._hooks, point_name: hooks}
        return reg

    def remove_hook(self, point_name: str, hook_name: str) -> bool:
        """Remove a hook by name from an extension point."""
        if point_name not in self._hooks:
            return False
        before = self._hooks[point_name]
        after = [h for h in before if h.name != hook_name]
        if len(after) == len(before):
            return False
        self._hooks = {**self._hooks, point_name: after}
        return True

    def get_hooks(self, point_name: str) -> list[HookRegistration]:
        """Return hooks for an extension point in priority order."""
        if point_name not in self._points:
            raise ExtensionPointNotFoundError(point_name)
        return list(self._hooks.get(point_name, []))

    # ---------------------------------------------------------------- invoke

    def invoke_sync(self, point_name: str, *args: Any, **kwargs: Any) -> list[Any]:
        """Invoke all sync hooks for an extension point, returning results.

        Async hooks are skipped. Results are in priority order.
        """
        hooks = self.get_hooks(point_name)
        results: list[Any] = []
        for hook in hooks:
            if hook.is_async:
                continue
            results.append(hook.callback(*args, **kwargs))
        return results

    async def invoke_async(self, point_name: str, *args: Any, **kwargs: Any) -> list[Any]:
        """Invoke all hooks (sync and async) for an extension point.

        Sync hooks are called directly; async hooks are awaited.
        Results are in priority order.
        """
        hooks = self.get_hooks(point_name)
        results: list[Any] = []
        for hook in hooks:
            if hook.is_async:
                results.append(await hook.callback(*args, **kwargs))
            else:
                results.append(hook.callback(*args, **kwargs))
        return results

    async def invoke_async_parallel(self, point_name: str, *args: Any, **kwargs: Any) -> list[Any]:
        """Invoke all async hooks in parallel, sync hooks sequentially first."""
        hooks = self.get_hooks(point_name)
        sync_results: list[Any] = []
        async_hooks: list[HookRegistration] = []

        for hook in hooks:
            if hook.is_async:
                async_hooks.append(hook)
            else:
                sync_results.append(hook.callback(*args, **kwargs))

        if async_hooks:
            async_results = await asyncio.gather(
                *(h.callback(*args, **kwargs) for h in async_hooks)
            )
            return [*sync_results, *list(async_results)]
        return sync_results

    # -------------------------------------------------------------- helpers

    def clear(self) -> None:
        """Remove all points and hooks."""
        self._points = {}
        self._hooks = {}

    def point_count(self) -> int:
        return len(self._points)

    def hook_count(self, point_name: str | None = None) -> int:
        """Total hooks, or hooks for a specific point."""
        if point_name is not None:
            return len(self._hooks.get(point_name, []))
        return sum(len(v) for v in self._hooks.values())

    def __contains__(self, name: object) -> bool:
        return name in self._points
