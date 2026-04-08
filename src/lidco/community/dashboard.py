"""Community Dashboard — stats, contributors, popular plugins, recent activity,
leaderboard (Task 1805)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActivityEntry:
    """A single community activity event."""

    actor: str
    action: str  # e.g. "published", "reviewed", "forked", "installed"
    target: str  # e.g. plugin/theme/recipe name
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "timestamp": self.timestamp,
        }


@dataclass
class ContributorStats:
    """Aggregated stats for a single contributor."""

    name: str
    plugins: int = 0
    themes: int = 0
    recipes: int = 0
    reviews: int = 0

    @property
    def score(self) -> int:
        """Contribution score: plugins*10, themes*5, recipes*5, reviews*1."""
        return self.plugins * 10 + self.themes * 5 + self.recipes * 5 + self.reviews

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "plugins": self.plugins,
            "themes": self.themes,
            "recipes": self.recipes,
            "reviews": self.reviews,
            "score": self.score,
        }


@dataclass
class CommunityStats:
    """Overall community statistics snapshot."""

    total_plugins: int = 0
    total_themes: int = 0
    total_recipes: int = 0
    total_contributors: int = 0
    total_downloads: int = 0
    total_reviews: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_plugins": self.total_plugins,
            "total_themes": self.total_themes,
            "total_recipes": self.total_recipes,
            "total_contributors": self.total_contributors,
            "total_downloads": self.total_downloads,
            "total_reviews": self.total_reviews,
        }


class CommunityDashboard:
    """Aggregated community dashboard with activity, leaderboard, and stats."""

    def __init__(self) -> None:
        self._activity: list[ActivityEntry] = []
        self._contributors: dict[str, ContributorStats] = {}
        self._stats: CommunityStats = CommunityStats()

    @property
    def activity_count(self) -> int:
        return len(self._activity)

    def record_activity(self, entry: ActivityEntry) -> None:
        """Record a community activity event."""
        self._activity.append(entry)
        self._ensure_contributor(entry.actor)

    def _ensure_contributor(self, name: str) -> ContributorStats:
        if name not in self._contributors:
            self._contributors[name] = ContributorStats(name=name)
        return self._contributors[name]

    def record_plugin(self, author: str, plugin_name: str) -> None:
        """Record a plugin publication."""
        cs = self._ensure_contributor(author)
        self._contributors[author] = ContributorStats(
            name=cs.name,
            plugins=cs.plugins + 1,
            themes=cs.themes,
            recipes=cs.recipes,
            reviews=cs.reviews,
        )
        self._stats = CommunityStats(
            total_plugins=self._stats.total_plugins + 1,
            total_themes=self._stats.total_themes,
            total_recipes=self._stats.total_recipes,
            total_contributors=len(self._contributors),
            total_downloads=self._stats.total_downloads,
            total_reviews=self._stats.total_reviews,
        )
        self.record_activity(ActivityEntry(actor=author, action="published", target=plugin_name))

    def record_theme(self, author: str, theme_name: str) -> None:
        """Record a theme publication."""
        cs = self._ensure_contributor(author)
        self._contributors[author] = ContributorStats(
            name=cs.name,
            plugins=cs.plugins,
            themes=cs.themes + 1,
            recipes=cs.recipes,
            reviews=cs.reviews,
        )
        self._stats = CommunityStats(
            total_plugins=self._stats.total_plugins,
            total_themes=self._stats.total_themes + 1,
            total_recipes=self._stats.total_recipes,
            total_contributors=len(self._contributors),
            total_downloads=self._stats.total_downloads,
            total_reviews=self._stats.total_reviews,
        )
        self.record_activity(ActivityEntry(actor=author, action="published", target=theme_name))

    def record_recipe(self, author: str, recipe_name: str) -> None:
        """Record a recipe publication."""
        cs = self._ensure_contributor(author)
        self._contributors[author] = ContributorStats(
            name=cs.name,
            plugins=cs.plugins,
            themes=cs.themes,
            recipes=cs.recipes + 1,
            reviews=cs.reviews,
        )
        self._stats = CommunityStats(
            total_plugins=self._stats.total_plugins,
            total_themes=self._stats.total_themes,
            total_recipes=self._stats.total_recipes + 1,
            total_contributors=len(self._contributors),
            total_downloads=self._stats.total_downloads,
            total_reviews=self._stats.total_reviews,
        )
        self.record_activity(ActivityEntry(actor=author, action="published", target=recipe_name))

    def record_review(self, author: str, target: str) -> None:
        """Record a review."""
        cs = self._ensure_contributor(author)
        self._contributors[author] = ContributorStats(
            name=cs.name,
            plugins=cs.plugins,
            themes=cs.themes,
            recipes=cs.recipes,
            reviews=cs.reviews + 1,
        )
        self._stats = CommunityStats(
            total_plugins=self._stats.total_plugins,
            total_themes=self._stats.total_themes,
            total_recipes=self._stats.total_recipes,
            total_contributors=len(self._contributors),
            total_downloads=self._stats.total_downloads,
            total_reviews=self._stats.total_reviews + 1,
        )
        self.record_activity(ActivityEntry(actor=author, action="reviewed", target=target))

    def record_download(self) -> None:
        """Increment global download counter."""
        self._stats = CommunityStats(
            total_plugins=self._stats.total_plugins,
            total_themes=self._stats.total_themes,
            total_recipes=self._stats.total_recipes,
            total_contributors=self._stats.total_contributors,
            total_downloads=self._stats.total_downloads + 1,
            total_reviews=self._stats.total_reviews,
        )

    def recent_activity(self, limit: int = 20) -> list[ActivityEntry]:
        """Most recent activity entries."""
        return list(reversed(self._activity[-limit:]))

    def leaderboard(self, limit: int = 10) -> list[ContributorStats]:
        """Top contributors by score."""
        contributors = list(self._contributors.values())
        return sorted(contributors, key=lambda c: c.score, reverse=True)[:limit]

    def get_contributor(self, name: str) -> ContributorStats | None:
        return self._contributors.get(name)

    def get_stats(self) -> CommunityStats:
        """Return current community stats snapshot."""
        return CommunityStats(
            total_plugins=self._stats.total_plugins,
            total_themes=self._stats.total_themes,
            total_recipes=self._stats.total_recipes,
            total_contributors=len(self._contributors),
            total_downloads=self._stats.total_downloads,
            total_reviews=self._stats.total_reviews,
        )

    def popular_plugins(self, plugins: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
        """Return top plugins by downloads from a provided list."""
        return sorted(plugins, key=lambda p: p.get("downloads", 0), reverse=True)[:limit]
