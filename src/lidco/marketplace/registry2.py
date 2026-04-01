"""Marketplace registry — central catalog of plugins (Task 1035)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from lidco.marketplace.manifest2 import (
    MarketplaceIndex,
    PluginCategory,
    PluginManifest2,
)


class MarketplaceRegistry:
    """Central registry for marketplace plugin manifests.

    Provides registration, search, category browsing, and
    import/export of the marketplace index.
    """

    def __init__(self, index: Optional[MarketplaceIndex] = None) -> None:
        self._index = index if index is not None else MarketplaceIndex()

    @property
    def index(self) -> MarketplaceIndex:
        return self._index

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, manifest: PluginManifest2) -> None:
        """Register a manifest in the registry.

        If a plugin with the same name already exists it is replaced.
        """
        existing = self._index.get(manifest.name)
        if existing is not None:
            self._index = self._index.remove(manifest.name)
        self._index = self._index.add(manifest)

    def unregister(self, name: str) -> bool:
        """Remove a manifest by name. Returns True if it existed."""
        if self._index.get(name) is None:
            return False
        self._index = self._index.remove(name)
        return True

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[PluginManifest2]:
        """Look up a manifest by name."""
        return self._index.get(name)

    def search(self, query: str) -> list[PluginManifest2]:
        """Search manifests by query substring."""
        return self._index.search(query)

    def categories(self) -> dict[str, list[PluginManifest2]]:
        """Return manifests grouped by category."""
        result: dict[str, list[PluginManifest2]] = {}
        for m in self._index.manifests:
            key = m.category.value
            if key not in result:
                result[key] = []
            result = {
                **result,
                key: [*result.get(key, []), m],
            }
        return result

    def list_all(self) -> list[PluginManifest2]:
        """Return all registered manifests."""
        return list(self._index.manifests)

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def export_index(
        self,
        path: str | Path,
        write_fn: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Write the full marketplace index as JSON."""
        data = {
            "version": "1.0",
            "plugins": [m.to_dict() for m in self._index.manifests],
        }
        content = json.dumps(data, indent=2)
        if write_fn is not None:
            write_fn(str(path), content)
        else:
            Path(path).write_text(content, encoding="utf-8")  # pragma: no cover

    def import_index(
        self,
        path: str | Path,
        read_fn: Optional[Callable[[str], str]] = None,
    ) -> int:
        """Load a marketplace index from JSON. Returns count of imported manifests."""
        if read_fn is not None:
            content = read_fn(str(path))
        else:
            content = Path(path).read_text(encoding="utf-8")  # pragma: no cover

        data = json.loads(content)
        plugins = data.get("plugins", [])
        count = 0
        for p in plugins:
            manifest = PluginManifest2.from_dict(p)
            self.register(manifest)
            count += 1
        return count

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._index)

    def __contains__(self, name: object) -> bool:
        return name in self._index


__all__ = [
    "MarketplaceRegistry",
]
