"""Plugin installer for MCP Marketplace (Task 949)."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from lidco.marketplace.manifest import PluginManifest


class InstallScope(Enum):
    """Scope of a plugin installation."""

    USER = "user"
    PROJECT = "project"


@dataclass
class InstalledPlugin:
    """Represents a plugin that has been installed."""

    manifest: PluginManifest
    scope: InstallScope
    installed_at: float
    install_path: str
    enabled: bool = True


class PluginInstaller:
    """Manages installation, removal, and status of plugins."""

    def __init__(
        self,
        install_dir: str = ".lidco/plugins",
        write_fn: Optional[Callable[[str, str], None]] = None,
        read_fn: Optional[Callable[[str], str]] = None,
        delete_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._install_dir = install_dir
        self._write_fn = write_fn or self._default_write
        self._read_fn = read_fn or self._default_read
        self._delete_fn = delete_fn or self._default_delete
        self._installed: dict[str, InstalledPlugin] = {}

    # ------------------------------------------------------------------
    # Default I/O helpers
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(
        self,
        manifest: PluginManifest,
        scope: InstallScope = InstallScope.PROJECT,
    ) -> InstalledPlugin:
        """Install a plugin from its manifest."""
        path = os.path.join(self._install_dir, manifest.name, "manifest.json")
        self._write_fn(path, json.dumps(manifest.to_dict(), indent=2))
        entry = InstalledPlugin(
            manifest=manifest,
            scope=scope,
            installed_at=time.time(),
            install_path=path,
            enabled=True,
        )
        self._installed[manifest.name] = entry
        return entry

    def uninstall(self, name: str) -> bool:
        """Remove an installed plugin. Returns *True* if it existed."""
        entry = self._installed.pop(name, None)
        if entry is None:
            return False
        self._delete_fn(entry.install_path)
        return True

    def update(self, name: str, new_manifest: PluginManifest) -> InstalledPlugin:
        """Update an already-installed plugin to a new manifest version."""
        old = self._installed.get(name)
        if old is None:
            raise KeyError(f"Plugin '{name}' is not installed")
        self.uninstall(name)
        return self.install(new_manifest, old.scope)

    def list_installed(self) -> list[InstalledPlugin]:
        """Return all installed plugins."""
        return list(self._installed.values())

    def is_installed(self, name: str) -> bool:
        """Check whether a plugin is installed."""
        return name in self._installed

    def enable(self, name: str) -> None:
        """Enable an installed plugin."""
        entry = self._installed.get(name)
        if entry is None:
            raise KeyError(f"Plugin '{name}' is not installed")
        self._installed[name] = InstalledPlugin(
            manifest=entry.manifest,
            scope=entry.scope,
            installed_at=entry.installed_at,
            install_path=entry.install_path,
            enabled=True,
        )

    def disable(self, name: str) -> None:
        """Disable an installed plugin."""
        entry = self._installed.get(name)
        if entry is None:
            raise KeyError(f"Plugin '{name}' is not installed")
        self._installed[name] = InstalledPlugin(
            manifest=entry.manifest,
            scope=entry.scope,
            installed_at=entry.installed_at,
            install_path=entry.install_path,
            enabled=False,
        )
