"""Managed settings loader with precedence-based merging."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ManagedSettingsError(Exception):
    """Error loading or merging managed settings."""


@dataclass(frozen=True)
class SettingsSource:
    """A single settings source."""

    path: str
    data: dict[str, Any]
    priority: int = 0
    source_type: str = "file"


class ManagedSettingsLoader:
    """Load and merge managed settings with precedence."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
        self._merged: dict[str, Any] = {}

    def load_file(self, path: str | Path) -> dict[str, Any]:
        """Load a single JSON settings file."""
        p = Path(path)
        if not p.is_absolute():
            p = self._base_dir / p
        try:
            text = p.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ManagedSettingsError(f"Expected dict in {p}, got {type(data).__name__}")
            return data
        except json.JSONDecodeError as exc:
            raise ManagedSettingsError(f"Invalid JSON in {p}: {exc}") from exc
        except OSError as exc:
            raise ManagedSettingsError(f"Cannot read {p}: {exc}") from exc

    def load_directory(self, path: str | Path) -> list[SettingsSource]:
        """Load all *.json files from a directory, sorted by name."""
        d = Path(path)
        if not d.is_absolute():
            d = self._base_dir / d
        if not d.is_dir():
            return []
        sources: list[SettingsSource] = []
        for f in sorted(d.glob("*.json")):
            try:
                data = self.load_file(f)
                sources.append(SettingsSource(path=str(f), data=data, priority=len(sources)))
            except ManagedSettingsError:
                continue
        return sources

    def merge(self, sources: list[SettingsSource]) -> dict[str, Any]:
        """Merge sources by priority (higher priority wins)."""
        sorted_sources = sorted(sources, key=lambda s: s.priority)
        merged: dict[str, Any] = {}
        for source in sorted_sources:
            merged = self._deep_merge(merged, source.data)
        self._merged = merged
        return dict(merged)

    def load_managed(self) -> dict[str, Any]:
        """Load managed-settings.json + managed-settings.d/ directory."""
        sources: list[SettingsSource] = []
        main_file = self._base_dir / "managed-settings.json"
        if main_file.exists():
            data = self.load_file(main_file)
            sources.append(SettingsSource(path=str(main_file), data=data, priority=0))
        dir_sources = self.load_directory(self._base_dir / "managed-settings.d")
        for i, s in enumerate(dir_sources):
            sources.append(SettingsSource(
                path=s.path, data=s.data, priority=i + 1, source_type=s.source_type
            ))
        return self.merge(sources)

    def get(self, key: str, default: Any = None) -> Any:
        """Dot-notation access into merged settings."""
        parts = key.split(".")
        current: Any = self._merged
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dicts. Override wins for non-dict values."""
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ManagedSettingsLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
