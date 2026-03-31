"""Graceful degradation: disable unhealthy subsystems automatically."""
from __future__ import annotations

from typing import Callable, Dict


class GracefulDegrader:
    """Manages subsystem health and auto-disables failing ones.

    Each subsystem has a health check function. When a health check
    fails, the subsystem is automatically disabled.
    """

    def __init__(self) -> None:
        self._subsystems: dict[str, Callable[[], bool]] = {}
        self._enabled: dict[str, bool] = {}

    def register_subsystem(
        self, name: str, health_check_fn: Callable[[], bool]
    ) -> None:
        """Register a subsystem with its health check function."""
        self._subsystems[name] = health_check_fn
        self._enabled[name] = True

    def disable(self, name: str) -> None:
        """Manually disable a subsystem."""
        if name not in self._subsystems:
            raise KeyError(f"Unknown subsystem: {name!r}")
        self._enabled[name] = False

    def enable(self, name: str) -> None:
        """Manually enable a subsystem."""
        if name not in self._subsystems:
            raise KeyError(f"Unknown subsystem: {name!r}")
        self._enabled[name] = True

    def is_healthy(self, name: str) -> bool:
        """Check if a subsystem is healthy (enabled and passes health check).

        If the health check fails, the subsystem is auto-disabled.
        """
        if name not in self._subsystems:
            raise KeyError(f"Unknown subsystem: {name!r}")
        if not self._enabled.get(name, False):
            return False
        try:
            healthy = self._subsystems[name]()
        except Exception:
            healthy = False
        if not healthy:
            self._enabled[name] = False
        return healthy

    def check_all(self) -> Dict[str, bool]:
        """Check all subsystems and return health status dict.

        Auto-disables any subsystem whose health check fails.
        """
        results: dict[str, bool] = {}
        for name in self._subsystems:
            results[name] = self.is_healthy(name)
        return results

    def list_subsystems(self) -> list[str]:
        """Return names of all registered subsystems."""
        return list(self._subsystems.keys())

    def enabled_subsystems(self) -> list[str]:
        """Return names of enabled subsystems."""
        return [n for n, e in self._enabled.items() if e]

    def disabled_subsystems(self) -> list[str]:
        """Return names of disabled subsystems."""
        return [n for n, e in self._enabled.items() if not e]
