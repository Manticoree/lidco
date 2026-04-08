"""Theme Gallery — shared themes, preview, one-click install, ratings, trending,
seasonal themes (Task 1803)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ThemeSeason(Enum):
    """Seasonal theme tag."""

    NONE = "none"
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"
    HOLIDAY = "holiday"


@dataclass
class ThemeColors:
    """Color palette for a theme."""

    primary: str = "#007acc"
    secondary: str = "#1e1e1e"
    background: str = "#1e1e1e"
    foreground: str = "#d4d4d4"
    accent: str = "#569cd6"
    error: str = "#f44747"
    warning: str = "#cca700"
    success: str = "#6a9955"

    def to_dict(self) -> dict[str, str]:
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "background": self.background,
            "foreground": self.foreground,
            "accent": self.accent,
            "error": self.error,
            "warning": self.warning,
            "success": self.success,
        }


@dataclass
class Theme:
    """A community theme."""

    name: str
    author: str
    description: str = ""
    colors: ThemeColors = field(default_factory=ThemeColors)
    season: ThemeSeason = ThemeSeason.NONE
    rating_sum: int = 0
    rating_count: int = 0
    installs: int = 0
    tags: list[str] = field(default_factory=list)
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = time.time()

    @property
    def average_rating(self) -> float:
        if self.rating_count == 0:
            return 0.0
        return self.rating_sum / self.rating_count

    def rate(self, score: int) -> Theme:
        """Return new Theme with rating added (immutable)."""
        if not 1 <= score <= 5:
            raise ValueError(f"Rating must be 1-5, got {score}")
        return Theme(
            name=self.name,
            author=self.author,
            description=self.description,
            colors=self.colors,
            season=self.season,
            rating_sum=self.rating_sum + score,
            rating_count=self.rating_count + 1,
            installs=self.installs,
            tags=list(self.tags),
            created_at=self.created_at,
        )

    def install(self) -> Theme:
        """Return new Theme with installs incremented."""
        return Theme(
            name=self.name,
            author=self.author,
            description=self.description,
            colors=self.colors,
            season=self.season,
            rating_sum=self.rating_sum,
            rating_count=self.rating_count,
            installs=self.installs + 1,
            tags=list(self.tags),
            created_at=self.created_at,
        )

    def preview(self) -> dict[str, Any]:
        """Generate a preview dict."""
        return {
            "name": self.name,
            "author": self.author,
            "colors": self.colors.to_dict(),
            "rating": self.average_rating,
            "installs": self.installs,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "author": self.author,
            "description": self.description,
            "colors": self.colors.to_dict(),
            "season": self.season.value,
            "average_rating": self.average_rating,
            "installs": self.installs,
            "tags": list(self.tags),
        }


class ThemeGallery:
    """Community theme gallery with browsing, rating, and seasonal themes."""

    def __init__(self) -> None:
        self._themes: dict[str, Theme] = {}
        self._installed: str = ""  # currently active theme name

    @property
    def count(self) -> int:
        return len(self._themes)

    @property
    def active_theme(self) -> str:
        return self._installed

    def add(self, theme: Theme) -> None:
        """Add or update a theme in the gallery."""
        if not theme.name:
            raise ValueError("Theme name is required")
        self._themes[theme.name] = theme

    def get(self, name: str) -> Theme | None:
        return self._themes.get(name)

    def remove(self, name: str) -> bool:
        if name in self._themes:
            del self._themes[name]
            if self._installed == name:
                self._installed = ""
            return True
        return False

    def install_theme(self, name: str) -> bool:
        """Install (activate) a theme. Returns False if not found."""
        theme = self._themes.get(name)
        if theme is None:
            return False
        self._themes[name] = theme.install()
        self._installed = name
        return True

    def rate_theme(self, name: str, score: int) -> bool:
        """Rate a theme. Returns False if not found."""
        theme = self._themes.get(name)
        if theme is None:
            return False
        self._themes[name] = theme.rate(score)
        return True

    def browse(self, limit: int = 50) -> list[Theme]:
        """Browse all themes sorted by installs."""
        themes = list(self._themes.values())
        return sorted(themes, key=lambda t: t.installs, reverse=True)[:limit]

    def trending(self, limit: int = 10) -> list[Theme]:
        """Top themes by rating count (engagement proxy)."""
        themes = [t for t in self._themes.values() if t.rating_count > 0]
        return sorted(themes, key=lambda t: t.rating_count, reverse=True)[:limit]

    def top_rated(self, limit: int = 10) -> list[Theme]:
        """Top themes by average rating."""
        themes = [t for t in self._themes.values() if t.rating_count > 0]
        return sorted(themes, key=lambda t: t.average_rating, reverse=True)[:limit]

    def seasonal(self, season: ThemeSeason) -> list[Theme]:
        """Return themes for a given season."""
        return [t for t in self._themes.values() if t.season == season]

    def search(self, query: str) -> list[Theme]:
        """Search themes by name/description/tags."""
        q = query.lower()
        results: list[Theme] = []
        for t in self._themes.values():
            if (
                q in t.name.lower()
                or q in t.description.lower()
                or any(q in tag.lower() for tag in t.tags)
            ):
                results.append(t)
        return sorted(results, key=lambda t: t.installs, reverse=True)

    def preview(self, name: str) -> dict[str, Any] | None:
        """Get a preview for a theme."""
        theme = self._themes.get(name)
        if theme is None:
            return None
        return theme.preview()

    def stats(self) -> dict[str, Any]:
        """Gallery statistics."""
        themes = list(self._themes.values())
        total_installs = sum(t.installs for t in themes)
        return {
            "total_themes": len(themes),
            "total_installs": total_installs,
            "seasons": sorted({t.season.value for t in themes}),
        }
