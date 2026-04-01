"""Keybinding registry — immutable keybinding management."""
from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class KeyBinding:
    """A single key binding definition."""

    keys: tuple[str, ...]
    action: str
    description: str = ""
    context: str = "global"


class KeybindingRegistry:
    """Immutable-style registry for key bindings.

    Every mutating method returns a **new** registry instance.
    """

    def __init__(self, bindings: tuple[KeyBinding, ...] = ()) -> None:
        self._bindings: tuple[KeyBinding, ...] = bindings

    @property
    def bindings(self) -> tuple[KeyBinding, ...]:
        return self._bindings

    def bind(
        self,
        keys: tuple[str, ...],
        action: str,
        description: str = "",
        context: str = "global",
    ) -> "KeybindingRegistry":
        """Return a new registry with *keys* bound to *action*."""
        binding = KeyBinding(keys=keys, action=action, description=description, context=context)
        # Replace existing binding with the same keys, if any
        new_bindings = tuple(b for b in self._bindings if b.keys != keys)
        return KeybindingRegistry((*new_bindings, binding))

    def unbind(self, keys: tuple[str, ...]) -> "KeybindingRegistry":
        """Return a new registry with the binding for *keys* removed."""
        new_bindings = tuple(b for b in self._bindings if b.keys != keys)
        return KeybindingRegistry(new_bindings)

    def lookup(self, keys: tuple[str, ...]) -> KeyBinding | None:
        """Find the binding matching *keys*, or ``None``."""
        for b in self._bindings:
            if b.keys == keys:
                return b
        return None

    def conflicts(self) -> list[tuple[KeyBinding, KeyBinding]]:
        """Return pairs of bindings that share the same key sequence."""
        seen: dict[tuple[str, ...], KeyBinding] = {}
        pairs: list[tuple[KeyBinding, KeyBinding]] = []
        for b in self._bindings:
            if b.keys in seen:
                pairs.append((seen[b.keys], b))
            else:
                seen[b.keys] = b
        return pairs

    def export_json(self) -> str:
        """Serialize all bindings to a JSON string."""
        data = [
            {
                "keys": list(b.keys),
                "action": b.action,
                "description": b.description,
                "context": b.context,
            }
            for b in self._bindings
        ]
        return json.dumps(data, indent=2)

    @classmethod
    def load_json(cls, data: str) -> "KeybindingRegistry":
        """Deserialize bindings from a JSON string."""
        items = json.loads(data)
        bindings = tuple(
            KeyBinding(
                keys=tuple(item["keys"]),
                action=item["action"],
                description=item.get("description", ""),
                context=item.get("context", "global"),
            )
            for item in items
        )
        return cls(bindings)
