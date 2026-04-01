"""Plugin installer v2 for Marketplace (Task 1034)."""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from lidco.marketplace.manifest2 import PluginManifest2


@dataclass(frozen=True)
class InstalledPlugin2:
    """Immutable record of an installed plugin."""

    name: str
    version: str
    path: str
    installed_at: float
    manifest: PluginManifest2
    checksum: str = ""


class PluginInstaller2:
    """Install, uninstall, update, and verify plugins."""

    def __init__(
        self,
        target_dir: str = ".lidco/marketplace_plugins",
        write_fn: Optional[Callable[[str, str], None]] = None,
        read_fn: Optional[Callable[[str], str]] = None,
        delete_fn: Optional[Callable[[str], None]] = None,
        exists_fn: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self._target_dir = target_dir
        self._write_fn = write_fn or self._default_write
        self._read_fn = read_fn or self._default_read
        self._delete_fn = delete_fn or self._default_delete
        self._exists_fn = exists_fn or self._default_exists
        self._installed: dict[str, InstalledPlugin2] = {}

    # ------------------------------------------------------------------
    # Default I/O
    # ------------------------------------------------------------------

    @staticmethod
    def _default_write(path: str, content: str) -> None:  # pragma: no cover
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)

    @staticmethod
    def _default_read(path: str) -> str:  # pragma: no cover
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def _default_delete(path: str) -> None:  # pragma: no cover
        if os.path.exists(path):
            os.remove(path)

    @staticmethod
    def _default_exists(path: str) -> bool:  # pragma: no cover
        return os.path.exists(path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _plugin_path(self, name: str) -> str:
        return os.path.join(self._target_dir, name, "manifest.json")

    @staticmethod
    def _compute_checksum(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(self, manifest: PluginManifest2) -> InstalledPlugin2:
        """Install a plugin from its manifest."""
        path = self._plugin_path(manifest.name)
        content = json.dumps(manifest.to_dict(), indent=2)
        self._write_fn(path, content)
        checksum = self._compute_checksum(content)
        entry = InstalledPlugin2(
            name=manifest.name,
            version=manifest.version,
            path=path,
            installed_at=time.time(),
            manifest=manifest,
            checksum=checksum,
        )
        self._installed = {**self._installed, manifest.name: entry}
        return entry

    def uninstall(self, plugin_name: str) -> bool:
        """Uninstall a plugin by name. Returns True if it was installed."""
        entry = self._installed.get(plugin_name)
        if entry is None:
            return False
        self._delete_fn(entry.path)
        self._installed = {k: v for k, v in self._installed.items() if k != plugin_name}
        return True

    def update(self, plugin_name: str, new_manifest: Optional[PluginManifest2] = None) -> InstalledPlugin2:
        """Update an installed plugin. Uses existing manifest if none provided."""
        old = self._installed.get(plugin_name)
        if old is None:
            raise KeyError(f"Plugin '{plugin_name}' is not installed")
        manifest = new_manifest if new_manifest is not None else old.manifest
        self.uninstall(plugin_name)
        return self.install(manifest)

    def list_installed(self) -> list[InstalledPlugin2]:
        """Return all installed plugins."""
        return list(self._installed.values())

    def get_installed(self, name: str) -> Optional[InstalledPlugin2]:
        """Get an installed plugin by name."""
        return self._installed.get(name)

    def is_installed(self, name: str) -> bool:
        """Check if a plugin is installed."""
        return name in self._installed

    def verify_integrity(self, plugin_name: str) -> bool:
        """Verify the installed plugin manifest matches its checksum."""
        entry = self._installed.get(plugin_name)
        if entry is None:
            return False
        try:
            content = self._read_fn(entry.path)
            return self._compute_checksum(content) == entry.checksum
        except Exception:
            return False


__all__ = [
    "InstalledPlugin2",
    "PluginInstaller2",
]
