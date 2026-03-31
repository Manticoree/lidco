"""Q128 — Configuration Profiles: ProfileManager."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from lidco.core.config import LidcoConfig
except ImportError:  # pragma: no cover
    LidcoConfig = None  # type: ignore[assignment,misc]


@dataclass
class ConfigProfile:
    name: str
    settings: dict
    description: str = ""
    is_active: bool = False
    created_at: str = ""


class ProfileManager:
    """Create and manage named configuration profiles."""

    def __init__(
        self,
        store_path: str = "/tmp/profiles.json",
        write_fn=None,
        read_fn=None,
    ) -> None:
        self._store_path = store_path
        self._write_fn = write_fn
        self._read_fn = read_fn
        self._profiles: dict[str, ConfigProfile] = {}
        self._load()

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        try:
            if self._read_fn:
                raw = self._read_fn(self._store_path)
            else:
                try:
                    with open(self._store_path, encoding="utf-8") as fh:
                        raw = fh.read()
                except FileNotFoundError:
                    return
            data = json.loads(raw)
            for item in data:
                p = ConfigProfile(**item)
                self._profiles[p.name] = p
        except Exception:
            pass

    def _save(self) -> None:
        raw = json.dumps(
            [vars(p) for p in self._profiles.values()], indent=2
        )
        try:
            if self._write_fn:
                self._write_fn(self._store_path, raw)
            else:
                with open(self._store_path, "w", encoding="utf-8") as fh:
                    fh.write(raw)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def create(
        self,
        name: str,
        settings: dict | None = None,
        description: str = "",
        config: "LidcoConfig | None" = None,
    ) -> ConfigProfile:
        """Create a new profile.

        Parameters
        ----------
        name:
            Profile name (unique key).
        settings:
            Explicit settings dict.  If *config* is also provided, the model
            snapshot is used instead.
        description:
            Optional human description.
        config:
            If provided, ``settings`` is populated from
            ``config.model_dump()`` so the profile captures the full config
            snapshot.
        """
        if config is not None and LidcoConfig is not None:
            resolved_settings: dict = config.model_dump()
        else:
            resolved_settings = dict(settings) if settings else {}
        ts = datetime.now(timezone.utc).isoformat()
        profile = ConfigProfile(
            name=name,
            settings=resolved_settings,
            description=description,
            is_active=False,
            created_at=ts,
        )
        self._profiles[name] = profile
        self._save()
        return profile

    def get(self, name: str) -> Optional[ConfigProfile]:
        return self._profiles.get(name)

    def list_all(self) -> list[ConfigProfile]:
        return list(self._profiles.values())

    def delete(self, name: str) -> bool:
        if name not in self._profiles:
            return False
        del self._profiles[name]
        self._save()
        return True

    def activate(self, name: str) -> ConfigProfile:
        if name not in self._profiles:
            raise KeyError(f"Profile '{name}' not found")
        for p in self._profiles.values():
            p.is_active = False
        self._profiles[name].is_active = True
        self._save()
        return self._profiles[name]

    def active(self) -> Optional[ConfigProfile]:
        for p in self._profiles.values():
            if p.is_active:
                return p
        return None

    def update(self, name: str, settings: dict) -> ConfigProfile:
        if name not in self._profiles:
            raise KeyError(f"Profile '{name}' not found")
        self._profiles[name].settings = {
            **self._profiles[name].settings,
            **settings,
        }
        self._save()
        return self._profiles[name]

    def export(self) -> str:
        return json.dumps([vars(p) for p in self._profiles.values()], indent=2)

    def import_profiles(self, json_str: str) -> int:
        items = json.loads(json_str)
        count = 0
        for item in items:
            p = ConfigProfile(**item)
            self._profiles[p.name] = p
            count += 1
        self._save()
        return count

    def apply_to(self, name: str, config: "LidcoConfig") -> "LidcoConfig":
        """Merge a profile's settings into a LidcoConfig, returning a new instance.

        Parameters
        ----------
        name:
            Profile name.
        config:
            The base ``LidcoConfig`` to merge into.

        Returns
        -------
        LidcoConfig
            A **new** config instance with the profile settings applied on top.

        Raises
        ------
        KeyError
            If the profile does not exist.
        """
        if name not in self._profiles:
            raise KeyError(f"Profile '{name}' not found")
        profile = self._profiles[name]
        if LidcoConfig is None:
            raise RuntimeError("LidcoConfig is not available")
        base = config.model_dump()
        merged = self._deep_merge(base, profile.settings)
        return LidcoConfig(**merged)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge *override* into *base* (returns new dict)."""
        result = deepcopy(base)
        for key, val in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = ProfileManager._deep_merge(result[key], val)
            else:
                result[key] = deepcopy(val)
        return result
