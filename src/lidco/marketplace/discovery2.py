"""Plugin discovery for Marketplace v2 (Task 1033)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from lidco.marketplace.manifest2 import (
    MarketplaceIndex,
    PluginCategory,
    PluginManifest2,
)


class SourceType(Enum):
    """Type of plugin source."""

    GIT = "git"
    NPM = "npm"
    LOCAL = "local"


@dataclass(frozen=True)
class SourceInfo:
    """Resolved source information."""

    source_type: SourceType
    url: str
    ref: str = ""


class PluginDiscovery2:
    """Plugin discovery with source resolution and search."""

    def __init__(self, index: Optional[MarketplaceIndex] = None) -> None:
        self._index = index if index is not None else MarketplaceIndex()

    @property
    def index(self) -> MarketplaceIndex:
        return self._index

    def set_index(self, index: MarketplaceIndex) -> "PluginDiscovery2":
        """Return a new discovery with an updated index (immutable)."""
        return PluginDiscovery2(index=index)

    def search(
        self,
        query: str,
        category: Optional[PluginCategory] = None,
    ) -> list[PluginManifest2]:
        """Search plugins by query string and optional category."""
        results = self._index.search(query)
        if category is not None:
            results = [m for m in results if m.category == category]
        return results

    def list_available(self) -> list[PluginManifest2]:
        """Return all available plugins."""
        return list(self._index.manifests)

    def list_by_category(self, category: PluginCategory) -> list[PluginManifest2]:
        """Return plugins in a specific category."""
        return self._index.filter_by_category(category)

    def get(self, name: str) -> Optional[PluginManifest2]:
        """Look up a plugin by name."""
        return self._index.get(name)

    @staticmethod
    def resolve_source(source_str: str) -> SourceInfo:
        """Resolve a source string to a SourceInfo.

        Rules:
        - Starts with ``git+`` or ends with ``.git`` -> GIT
        - Starts with ``npm:`` -> NPM
        - Everything else -> LOCAL
        """
        s = source_str.strip()
        if not s:
            return SourceInfo(source_type=SourceType.LOCAL, url="")

        if s.startswith("git+"):
            url = s[4:]
            parts = url.rsplit("@", 1)
            if len(parts) == 2 and not parts[1].startswith("/"):
                return SourceInfo(source_type=SourceType.GIT, url=parts[0], ref=parts[1])
            return SourceInfo(source_type=SourceType.GIT, url=url)

        if s.endswith(".git"):
            return SourceInfo(source_type=SourceType.GIT, url=s)

        if s.startswith("npm:"):
            return SourceInfo(source_type=SourceType.NPM, url=s[4:])

        return SourceInfo(source_type=SourceType.LOCAL, url=s)

    def fetch_manifest(
        self,
        source: SourceInfo,
        read_fn: Optional[object] = None,
    ) -> PluginManifest2:
        """Fetch a manifest from a source.

        For LOCAL sources, reads ``manifest.json`` from the path.
        For GIT/NPM, raises NotImplementedError (requires network).
        """
        if source.source_type == SourceType.LOCAL:
            import json
            from lidco.marketplace.manifest2 import load_manifest

            path = source.url.rstrip("/") + "/manifest.json"
            if read_fn is not None:
                content = read_fn(path)  # type: ignore[operator]
                data = json.loads(content)
                return PluginManifest2.from_dict(data)
            return load_manifest(path)

        raise NotImplementedError(
            f"Fetching from {source.source_type.value} sources is not yet supported"
        )


__all__ = [
    "PluginDiscovery2",
    "SourceInfo",
    "SourceType",
]
