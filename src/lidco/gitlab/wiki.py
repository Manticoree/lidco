"""
GitLab wiki page management (simulated).

Read, create, update, search, and list wiki pages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WikiPage:
    """Represents a GitLab wiki page."""

    slug: str
    title: str
    content: str
    format: str = "markdown"


class GitLabWiki:
    """Simulated GitLab project wiki."""

    def __init__(self) -> None:
        self._pages: dict[str, WikiPage] = {}

    def get_page(self, slug: str) -> WikiPage:
        """Retrieve a wiki page by slug."""
        if slug not in self._pages:
            raise KeyError(f"Wiki page '{slug}' not found")
        return self._pages[slug]

    def create_page(self, title: str, content: str) -> WikiPage:
        """Create a new wiki page. Slug is derived from title."""
        if not title.strip():
            raise ValueError("Title must not be empty")
        slug = title.lower().replace(" ", "-")
        if slug in self._pages:
            raise ValueError(f"Page '{slug}' already exists")
        page = WikiPage(slug=slug, title=title, content=content)
        self._pages[slug] = page
        return page

    def update_page(self, slug: str, content: str) -> WikiPage:
        """Update an existing wiki page's content."""
        if slug not in self._pages:
            raise KeyError(f"Wiki page '{slug}' not found")
        page = self._pages[slug]
        updated = WikiPage(
            slug=page.slug,
            title=page.title,
            content=content,
            format=page.format,
        )
        self._pages[slug] = updated
        return updated

    def search(self, query: str) -> list[WikiPage]:
        """Search wiki pages by title or content substring."""
        if not query.strip():
            return []
        q = query.lower()
        return [
            p for p in self._pages.values()
            if q in p.title.lower() or q in p.content.lower()
        ]

    def list_pages(self) -> list[WikiPage]:
        """List all wiki pages sorted by slug."""
        return sorted(self._pages.values(), key=lambda p: p.slug)
