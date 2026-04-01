"""Team knowledge base with snippet library and voting."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import time


_counter = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    return f"snip_{_counter}"


@dataclass(frozen=True)
class Snippet:
    id: str
    title: str
    content: str
    author: str
    tags: tuple[str, ...] = ()
    upvotes: int = 0
    created_at: float = field(default_factory=time.time)


class KnowledgeShare:
    """Team knowledge base with snippet library and voting."""

    def __init__(self) -> None:
        self._snippets: dict[str, Snippet] = {}

    def add_snippet(
        self,
        title: str,
        content: str,
        author: str,
        tags: tuple[str, ...] = (),
    ) -> Snippet:
        snippet = Snippet(
            id=_next_id(),
            title=title,
            content=content,
            author=author,
            tags=tags,
        )
        self._snippets = {**self._snippets, snippet.id: snippet}
        return snippet

    def get_snippet(self, snippet_id: str) -> Snippet | None:
        return self._snippets.get(snippet_id)

    def search(self, query: str) -> list[Snippet]:
        q = query.lower()
        results: list[Snippet] = []
        for s in self._snippets.values():
            if (
                q in s.title.lower()
                or q in s.content.lower()
                or any(q in t.lower() for t in s.tags)
            ):
                results.append(s)
        return results

    def upvote(self, snippet_id: str) -> Snippet | None:
        s = self._snippets.get(snippet_id)
        if s is None:
            return None
        updated = Snippet(
            id=s.id,
            title=s.title,
            content=s.content,
            author=s.author,
            tags=s.tags,
            upvotes=s.upvotes + 1,
            created_at=s.created_at,
        )
        self._snippets = {**self._snippets, s.id: updated}
        return updated

    def remove_snippet(self, snippet_id: str) -> bool:
        if snippet_id not in self._snippets:
            return False
        self._snippets = {
            k: v for k, v in self._snippets.items() if k != snippet_id
        }
        return True

    def list_by_tag(self, tag: str) -> list[Snippet]:
        return [s for s in self._snippets.values() if tag in s.tags]

    def top_snippets(self, limit: int = 10) -> list[Snippet]:
        return sorted(
            self._snippets.values(), key=lambda s: s.upvotes, reverse=True
        )[:limit]

    def suggest_for_context(self, context: str) -> list[Snippet]:
        words = context.lower().split()
        results: list[Snippet] = []
        for s in self._snippets.values():
            text = f"{s.title} {s.content} {' '.join(s.tags)}".lower()
            if any(w in text for w in words if len(w) > 2):
                results.append(s)
        return results

    def export_all(self) -> list[dict]:
        return [
            {
                "id": s.id,
                "title": s.title,
                "content": s.content,
                "author": s.author,
                "tags": list(s.tags),
                "upvotes": s.upvotes,
            }
            for s in self._snippets.values()
        ]

    def summary(self) -> str:
        total = len(self._snippets)
        total_votes = sum(s.upvotes for s in self._snippets.values())
        lines = [
            f"Snippets: {total}",
            f"Total upvotes: {total_votes}",
        ]
        return "\n".join(lines)
