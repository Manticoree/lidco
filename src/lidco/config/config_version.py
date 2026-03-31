"""Q144 — Configuration Migration & Versioning: ConfigVersion."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VersionedConfig:
    """A version-stamped configuration."""

    version: str
    data: dict
    created_at: float = field(default_factory=time.time)
    migrated_from: Optional[str] = None


class ConfigVersion:
    """Stamp, inspect, and compare config versions."""

    VERSION_KEY = "__config_version__"
    CREATED_KEY = "__config_created_at__"
    MIGRATED_KEY = "__config_migrated_from__"

    def stamp(self, data: dict, version: str) -> VersionedConfig:
        """Add version metadata to *data* and return a VersionedConfig."""
        now = time.time()
        stamped = {
            **data,
            self.VERSION_KEY: version,
            self.CREATED_KEY: now,
        }
        return VersionedConfig(version=version, data=stamped, created_at=now)

    def get_version(self, data: dict) -> Optional[str]:
        """Extract the version string from a config dict, or None."""
        return data.get(self.VERSION_KEY)

    def is_current(self, data: dict, current_version: str) -> bool:
        """Return True if *data* is already at *current_version*."""
        return self.get_version(data) == current_version

    def needs_migration(self, data: dict, current_version: str) -> bool:
        """Return True if *data* has a version that differs from *current_version*."""
        v = self.get_version(data)
        if v is None:
            return True
        return v != current_version

    def compare_versions(self, a: str, b: str) -> int:
        """Compare two semver strings. Returns -1 / 0 / 1."""
        pa = self.parse_version(a)
        pb = self.parse_version(b)
        if pa < pb:
            return -1
        if pa > pb:
            return 1
        return 0

    @staticmethod
    def parse_version(v: str) -> tuple[int, int, int]:
        """Split ``'1.2.3'`` into ``(1, 2, 3)``."""
        parts = v.strip().split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid semver: {v!r}")
        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            raise ValueError(f"Invalid semver: {v!r}")
