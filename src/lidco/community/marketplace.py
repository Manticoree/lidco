"""Plugin Marketplace v2 — community plugins, ratings, reviews, downloads, auto-update,
compatibility matrix (Task 1802)."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PluginStatus(Enum):
    """Lifecycle status of a marketplace plugin."""

    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


@dataclass
class PluginReview:
    """A user review for a plugin."""

    author: str
    rating: int  # 1-5
    comment: str = ""
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if not 1 <= self.rating <= 5:
            raise ValueError(f"Rating must be 1-5, got {self.rating}")
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class CompatEntry:
    """Records whether a plugin version is compatible with a LIDCO version."""

    plugin_version: str
    lidco_version: str
    compatible: bool
    tested_at: float = 0.0


@dataclass
class MarketplacePlugin:
    """A plugin listed on the marketplace."""

    name: str
    version: str
    description: str
    author: str
    category: str = "general"
    status: PluginStatus = PluginStatus.PUBLISHED
    downloads: int = 0
    reviews: list[PluginReview] = field(default_factory=list)
    compat_matrix: list[CompatEntry] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self) -> None:
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @property
    def average_rating(self) -> float:
        if not self.reviews:
            return 0.0
        return sum(r.rating for r in self.reviews) / len(self.reviews)

    @property
    def review_count(self) -> int:
        return len(self.reviews)

    def add_review(self, review: PluginReview) -> MarketplacePlugin:
        """Return new plugin with the review added (immutable)."""
        return MarketplacePlugin(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            category=self.category,
            status=self.status,
            downloads=self.downloads,
            reviews=[*self.reviews, review],
            compat_matrix=list(self.compat_matrix),
            tags=list(self.tags),
            created_at=self.created_at,
            updated_at=time.time(),
        )

    def increment_downloads(self) -> MarketplacePlugin:
        """Return new plugin with downloads incremented."""
        return MarketplacePlugin(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            category=self.category,
            status=self.status,
            downloads=self.downloads + 1,
            reviews=list(self.reviews),
            compat_matrix=list(self.compat_matrix),
            tags=list(self.tags),
            created_at=self.created_at,
            updated_at=time.time(),
        )

    def add_compat_entry(self, entry: CompatEntry) -> MarketplacePlugin:
        """Return new plugin with compatibility entry added."""
        return MarketplacePlugin(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            category=self.category,
            status=self.status,
            downloads=self.downloads,
            reviews=list(self.reviews),
            compat_matrix=[*self.compat_matrix, entry],
            tags=list(self.tags),
            created_at=self.created_at,
            updated_at=time.time(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "status": self.status.value,
            "downloads": self.downloads,
            "average_rating": self.average_rating,
            "review_count": self.review_count,
            "tags": list(self.tags),
        }


class PluginMarketplaceV2:
    """Community plugin marketplace with ratings, reviews, and auto-update."""

    def __init__(self) -> None:
        self._plugins: dict[str, MarketplacePlugin] = {}
        self._update_registry: dict[str, str] = {}  # name -> latest version

    @property
    def count(self) -> int:
        return len(self._plugins)

    def publish(self, plugin: MarketplacePlugin) -> None:
        """Publish or update a plugin."""
        if not plugin.name:
            raise ValueError("Plugin name is required")
        self._plugins[plugin.name] = plugin
        cur = self._update_registry.get(plugin.name, "0.0.0")
        if plugin.version >= cur:
            self._update_registry[plugin.name] = plugin.version

    def get(self, name: str) -> MarketplacePlugin | None:
        return self._plugins.get(name)

    def remove(self, name: str) -> bool:
        if name in self._plugins:
            del self._plugins[name]
            self._update_registry.pop(name, None)
            return True
        return False

    def search(self, query: str, category: str | None = None) -> list[MarketplacePlugin]:
        """Search plugins by name/description/tags, optionally filtered by category."""
        q = query.lower()
        results: list[MarketplacePlugin] = []
        for p in self._plugins.values():
            if p.status != PluginStatus.PUBLISHED:
                continue
            if category and p.category != category:
                continue
            if (
                q in p.name.lower()
                or q in p.description.lower()
                or any(q in t.lower() for t in p.tags)
            ):
                results.append(p)
        return sorted(results, key=lambda x: x.downloads, reverse=True)

    def browse(self, category: str | None = None, limit: int = 50) -> list[MarketplacePlugin]:
        """Browse published plugins, optionally by category."""
        results = [
            p for p in self._plugins.values()
            if p.status == PluginStatus.PUBLISHED
            and (category is None or p.category == category)
        ]
        return sorted(results, key=lambda x: x.downloads, reverse=True)[:limit]

    def top_rated(self, limit: int = 10) -> list[MarketplacePlugin]:
        """Return plugins sorted by average rating."""
        rated = [p for p in self._plugins.values() if p.review_count > 0]
        return sorted(rated, key=lambda x: x.average_rating, reverse=True)[:limit]

    def add_review(self, plugin_name: str, review: PluginReview) -> bool:
        """Add a review to a plugin. Returns False if plugin not found."""
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            return False
        self._plugins[plugin_name] = plugin.add_review(review)
        return True

    def record_download(self, plugin_name: str) -> bool:
        """Increment download counter. Returns False if not found."""
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            return False
        self._plugins[plugin_name] = plugin.increment_downloads()
        return True

    def check_update(self, name: str, current_version: str) -> str | None:
        """Return latest version if newer than *current_version*, else None."""
        latest = self._update_registry.get(name)
        if latest and latest > current_version:
            return latest
        return None

    def compat_matrix(self, plugin_name: str) -> list[CompatEntry]:
        """Return compatibility entries for a plugin."""
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            return []
        return list(plugin.compat_matrix)

    def add_compat_entry(self, plugin_name: str, entry: CompatEntry) -> bool:
        """Add a compatibility entry. Returns False if plugin not found."""
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            return False
        self._plugins[plugin_name] = plugin.add_compat_entry(entry)
        return True

    def stats(self) -> dict[str, Any]:
        """Return marketplace statistics."""
        plugins = list(self._plugins.values())
        total_downloads = sum(p.downloads for p in plugins)
        total_reviews = sum(p.review_count for p in plugins)
        categories: set[str] = {p.category for p in plugins}
        return {
            "total_plugins": len(plugins),
            "total_downloads": total_downloads,
            "total_reviews": total_reviews,
            "categories": sorted(categories),
        }
