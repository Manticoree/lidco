"""Settings hierarchy: user -> project -> org -> managed."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SettingsLayer:
    """A single layer in the settings hierarchy."""

    name: str
    data: dict[str, Any]
    priority: int


class SettingsHierarchy:
    """Merge multiple settings layers by priority."""

    def __init__(self) -> None:
        self._layers: dict[str, SettingsLayer] = {}

    def add_layer(self, name: str, data: dict[str, Any], priority: int) -> None:
        """Add or replace a named layer."""
        self._layers[name] = SettingsLayer(name=name, data=data, priority=priority)

    def remove_layer(self, name: str) -> bool:
        """Remove a layer by name. Returns True if it existed."""
        return self._layers.pop(name, None) is not None

    def resolve(self, key: str, default: Any = None) -> Any:
        """Resolve a dot-notation key. Highest priority layer wins."""
        sorted_layers = sorted(self._layers.values(), key=lambda l: l.priority, reverse=True)
        for layer in sorted_layers:
            val = self._get_nested(layer.data, key)
            if val is not _MISSING:
                return val
        return default

    def resolve_all(self) -> dict[str, Any]:
        """Return fully merged settings (lower priority first, higher overrides)."""
        sorted_layers = sorted(self._layers.values(), key=lambda l: l.priority)
        merged: dict[str, Any] = {}
        for layer in sorted_layers:
            merged = self._deep_merge(merged, layer.data)
        return merged

    def list_layers(self) -> list[SettingsLayer]:
        """Return all layers sorted by priority (ascending)."""
        return sorted(self._layers.values(), key=lambda l: l.priority)

    def diff(self, layer1_name: str, layer2_name: str) -> dict[str, tuple[Any, Any]]:
        """Return keys that differ between two layers as {key: (val1, val2)}."""
        l1 = self._layers.get(layer1_name)
        l2 = self._layers.get(layer2_name)
        if l1 is None or l2 is None:
            return {}
        d1 = self._flatten(l1.data)
        d2 = self._flatten(l2.data)
        all_keys = set(d1) | set(d2)
        result: dict[str, tuple[Any, Any]] = {}
        for k in sorted(all_keys):
            v1 = d1.get(k, _MISSING)
            v2 = d2.get(k, _MISSING)
            if v1 != v2:
                result[k] = (
                    v1 if v1 is not _MISSING else None,
                    v2 if v2 is not _MISSING else None,
                )
        return result

    def summary(self) -> str:
        """Human-readable summary."""
        layers = self.list_layers()
        lines = [f"SettingsHierarchy: {len(layers)} layers"]
        for layer in layers:
            lines.append(f"  {layer.name} (priority={layer.priority}): {len(layer.data)} top-level keys")
        return "\n".join(lines)

    @staticmethod
    def _get_nested(data: dict[str, Any], key: str) -> Any:
        """Dot-notation lookup. Returns _MISSING if not found."""
        parts = key.split(".")
        current: Any = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return _MISSING
        return current

    @staticmethod
    def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        """Flatten nested dict to dot-notation keys."""
        result: dict[str, Any] = {}
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                result.update(SettingsHierarchy._flatten(v, full_key))
            else:
                result[full_key] = v
        return result

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dicts."""
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = SettingsHierarchy._deep_merge(result[key], value)
            else:
                result[key] = value
        return result


class _MissingSentinel:
    """Sentinel for missing values."""

    def __repr__(self) -> str:
        return "<MISSING>"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _MissingSentinel)

    def __hash__(self) -> int:
        return hash("_MISSING")


_MISSING = _MissingSentinel()
