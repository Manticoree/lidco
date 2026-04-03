"""Shortcut registry with conflict detection and context-dependent bindings."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Shortcut:
    """A keyboard shortcut binding."""

    keys: str
    command: str
    description: str = ""
    context: str = "global"
    enabled: bool = True


class ShortcutRegistry:
    """Register keyboard shortcuts; conflict detection; context-dependent; chord sequences."""

    def __init__(self) -> None:
        # (keys_normalised, context) -> Shortcut
        self._shortcuts: dict[tuple[str, str], Shortcut] = {}

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(keys: str) -> str:
        """Lower-case and collapse whitespace in key strings."""
        return " ".join(keys.lower().split())

    def _key(self, keys: str, context: str) -> tuple[str, str]:
        return (self._normalise(keys), context)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def register(self, shortcut: Shortcut) -> Shortcut:
        """Register *shortcut*.  Raises ``ValueError`` on conflict in same context."""
        k = self._key(shortcut.keys, shortcut.context)
        if k in self._shortcuts:
            existing = self._shortcuts[k]
            raise ValueError(
                f"Shortcut '{shortcut.keys}' already registered in context "
                f"'{shortcut.context}' for command '{existing.command}'"
            )
        self._shortcuts[k] = shortcut
        return shortcut

    def unregister(self, keys: str, context: str = "global") -> bool:
        k = self._key(keys, context)
        if k in self._shortcuts:
            del self._shortcuts[k]
            return True
        return False

    def get(self, keys: str, context: str = "global") -> Shortcut | None:
        return self._shortcuts.get(self._key(keys, context))

    def find_by_command(self, command: str) -> list[Shortcut]:
        return [s for s in self._shortcuts.values() if s.command == command]

    def conflicts(self, keys: str, context: str = "global") -> list[Shortcut]:
        """Return shortcuts that conflict with *keys* in *context*."""
        k = self._key(keys, context)
        result: list[Shortcut] = []
        if k in self._shortcuts:
            result.append(self._shortcuts[k])
        return result

    def all_shortcuts(self, context: str | None = None) -> list[Shortcut]:
        if context is None:
            return list(self._shortcuts.values())
        return [s for s in self._shortcuts.values() if s.context == context]

    def enable(self, keys: str, context: str = "global") -> bool:
        s = self.get(keys, context)
        if s is None:
            return False
        s.enabled = True
        return True

    def disable(self, keys: str, context: str = "global") -> bool:
        s = self.get(keys, context)
        if s is None:
            return False
        s.enabled = False
        return True

    def summary(self) -> dict:
        total = len(self._shortcuts)
        enabled = sum(1 for s in self._shortcuts.values() if s.enabled)
        contexts = sorted({s.context for s in self._shortcuts.values()})
        return {
            "total": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "contexts": contexts,
        }
