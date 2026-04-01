"""Plugin Marketplace manifest v2 — extended manifest with categories (Task 1032)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class PluginCategory(Enum):
    """Plugin category classification."""

    DEVELOPMENT = "development"
    PRODUCTIVITY = "productivity"
    LEARNING = "learning"
    SECURITY = "security"


@dataclass(frozen=True)
class AuthorInfo:
    """Immutable author information."""

    name: str
    email: str = ""


@dataclass(frozen=True)
class PluginManifest2:
    """Extended plugin manifest with category, author info, and source."""

    name: str
    version: str
    description: str
    author: AuthorInfo
    category: PluginCategory
    source: str = ""
    dependencies: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    homepage: str = ""
    license: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": {"name": self.author.name, "email": self.author.email},
            "category": self.category.value,
            "source": self.source,
            "dependencies": list(self.dependencies),
            "tags": list(self.tags),
            "homepage": self.homepage,
            "license": self.license,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginManifest2:
        """Create from a plain dictionary."""
        author_raw = data.get("author", {})
        if isinstance(author_raw, str):
            author = AuthorInfo(name=author_raw)
        elif isinstance(author_raw, dict):
            author = AuthorInfo(
                name=author_raw.get("name", ""),
                email=author_raw.get("email", ""),
            )
        else:
            author = AuthorInfo(name="")

        cat_raw = data.get("category", "development")
        if isinstance(cat_raw, PluginCategory):
            category = cat_raw
        else:
            category = PluginCategory(cat_raw)

        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            description=data.get("description", ""),
            author=author,
            category=category,
            source=data.get("source", ""),
            dependencies=tuple(data.get("dependencies", [])),
            tags=tuple(data.get("tags", [])),
            homepage=data.get("homepage", ""),
            license=data.get("license", ""),
        )


class PluginManifestSchema:
    """Validate manifest JSON data."""

    REQUIRED_FIELDS = ("name", "version", "description", "author", "category")

    _SEMVER_PATTERN = r"^\d+\.\d+\.\d+"

    @classmethod
    def validate(cls, data: dict[str, Any]) -> list[str]:
        """Return a list of validation errors (empty means valid)."""
        import re

        errors: list[str] = []
        for f in cls.REQUIRED_FIELDS:
            val = data.get(f)
            if not val:
                errors.append(f"{f} is required")

        version = data.get("version", "")
        if version and not re.match(cls._SEMVER_PATTERN, version):
            errors.append("version must follow semver (e.g. 1.0.0)")

        cat = data.get("category", "")
        if cat:
            valid_cats = {c.value for c in PluginCategory}
            if cat not in valid_cats:
                errors.append(f"category must be one of: {', '.join(sorted(valid_cats))}")

        author = data.get("author")
        if isinstance(author, dict) and not author.get("name"):
            errors.append("author.name is required")

        return errors


def load_manifest(path: str | Path, read_fn: Any = None) -> PluginManifest2:
    """Load a plugin manifest from a JSON file."""
    if read_fn is not None:
        content = read_fn(str(path))
    else:
        content = Path(path).read_text(encoding="utf-8")  # pragma: no cover
    data = json.loads(content)
    errors = PluginManifestSchema.validate(data)
    if errors:
        raise ValueError(f"Invalid manifest: {'; '.join(errors)}")
    return PluginManifest2.from_dict(data)


def save_manifest(
    manifest: PluginManifest2,
    path: str | Path,
    write_fn: Any = None,
) -> None:
    """Save a plugin manifest to a JSON file."""
    content = json.dumps(manifest.to_dict(), indent=2)
    if write_fn is not None:
        write_fn(str(path), content)
    else:
        Path(path).write_text(content, encoding="utf-8")  # pragma: no cover


class MarketplaceIndex:
    """Collection of manifests with search and filter capabilities."""

    def __init__(self, manifests: Optional[list[PluginManifest2]] = None) -> None:
        self._manifests: tuple[PluginManifest2, ...] = tuple(manifests) if manifests else ()

    @property
    def manifests(self) -> tuple[PluginManifest2, ...]:
        return self._manifests

    def add(self, manifest: PluginManifest2) -> "MarketplaceIndex":
        """Return a new index with the manifest added (immutable)."""
        return MarketplaceIndex(list(self._manifests) + [manifest])

    def remove(self, name: str) -> "MarketplaceIndex":
        """Return a new index without the named manifest (immutable)."""
        return MarketplaceIndex([m for m in self._manifests if m.name != name])

    def search(self, query: str) -> list[PluginManifest2]:
        """Search manifests by name or description substring."""
        q = query.lower()
        return [
            m for m in self._manifests
            if q in m.name.lower() or q in m.description.lower()
        ]

    def filter_by_category(self, category: PluginCategory) -> list[PluginManifest2]:
        """Filter manifests by category."""
        return [m for m in self._manifests if m.category == category]

    def filter_by_author(self, author_name: str) -> list[PluginManifest2]:
        """Filter manifests by author name."""
        return [m for m in self._manifests if m.author.name == author_name]

    def get(self, name: str) -> Optional[PluginManifest2]:
        """Look up a manifest by exact name."""
        for m in self._manifests:
            if m.name == name:
                return m
        return None

    def categories(self) -> dict[str, int]:
        """Return category counts."""
        counts: dict[str, int] = {}
        for m in self._manifests:
            key = m.category.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def __len__(self) -> int:
        return len(self._manifests)

    def __contains__(self, name: object) -> bool:
        return any(m.name == name for m in self._manifests)


__all__ = [
    "AuthorInfo",
    "MarketplaceIndex",
    "PluginCategory",
    "PluginManifest2",
    "PluginManifestSchema",
    "load_manifest",
    "save_manifest",
]
