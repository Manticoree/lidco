"""Plugin discovery for MCP Marketplace (Task 948)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from lidco.marketplace.manifest import PluginManifest, TrustLevel


@dataclass
class SearchResult:
    """Result of a plugin search."""

    plugins: list[PluginManifest] = field(default_factory=list)
    total: int = 0
    query: str = ""


class PluginDiscovery:
    """In-memory plugin registry and search."""

    def __init__(self, registry: Optional[list[PluginManifest]] = None) -> None:
        self._registry: list[PluginManifest] = list(registry) if registry else []

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_plugin(self, manifest: PluginManifest) -> None:
        """Register a plugin manifest."""
        self._registry.append(manifest)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        trust_level: Optional[TrustLevel] = None,
    ) -> SearchResult:
        """Search plugins by query string, optional category and trust level."""
        q_lower = query.lower()
        results: list[PluginManifest] = []
        for p in self._registry:
            if q_lower not in p.name.lower() and q_lower not in p.description.lower():
                continue
            if category is not None and p.category != category:
                continue
            if trust_level is not None and p.trust_level != trust_level:
                continue
            results.append(p)
        return SearchResult(plugins=results, total=len(results), query=query)

    def browse(
        self,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> list[PluginManifest]:
        """Browse plugins with optional category filter."""
        results: list[PluginManifest] = []
        for p in self._registry:
            if category is not None and p.category != category:
                continue
            results.append(p)
            if len(results) >= limit:
                break
        return results

    def get(self, name: str) -> Optional[PluginManifest]:
        """Look up a plugin by exact name."""
        for p in self._registry:
            if p.name == name:
                return p
        return None

    def categories(self) -> list[str]:
        """Return unique categories across all registered plugins."""
        seen: set[str] = set()
        out: list[str] = []
        for p in self._registry:
            if p.category and p.category not in seen:
                seen.add(p.category)
                out.append(p.category)
        return out

    def by_author(self, author: str) -> list[PluginManifest]:
        """Return plugins by a specific author."""
        return [p for p in self._registry if p.author == author]
