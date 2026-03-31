"""Context-aware completion engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lidco.completion.trie import CompletionTrie


@dataclass
class CompletionItem:
    """A single completion suggestion."""

    text: str
    category: str  # "command" | "file" | "symbol" | "argument"
    score: float
    description: str = ""


class ContextCompleter:
    """Provides context-aware autocompletion across multiple sources."""

    def __init__(self) -> None:
        self._tries: dict[str, CompletionTrie] = {}
        self._descriptions: dict[str, dict[str, str]] = {}

    def add_source(
        self,
        category: str,
        items: list[str],
        descriptions: dict[str, str] | None = None,
    ) -> None:
        """Register a completion source under *category*."""
        trie = CompletionTrie()
        for item in items:
            trie.insert(item)
        self._tries[category] = trie
        self._descriptions[category] = descriptions or {}

    def complete(
        self, input_text: str, cursor_pos: int | None = None
    ) -> list[CompletionItem]:
        """Return context-aware completions for *input_text*.

        If *cursor_pos* is given, only the text up to that position is
        considered for matching.
        """
        if cursor_pos is not None:
            text = input_text[:cursor_pos]
        else:
            text = input_text

        prefix = text.strip().split()[-1] if text.strip() else ""
        if not prefix:
            return []

        # Determine category from context
        if prefix.startswith("/"):
            return self.complete_command(prefix)
        if "/" in prefix or "\\" in prefix or prefix.startswith("."):
            return self.complete_path(prefix)

        # Search all sources
        results: list[CompletionItem] = []
        for category, trie in self._tries.items():
            matches = trie.search(prefix)
            descs = self._descriptions.get(category, {})
            for match in matches:
                score = 1.0 if match == prefix else 0.5
                results.append(
                    CompletionItem(
                        text=match,
                        category=category,
                        score=score,
                        description=descs.get(match, ""),
                    )
                )
        results.sort(key=lambda c: (-c.score, c.text))
        return results

    def complete_command(self, prefix: str) -> list[CompletionItem]:
        """Complete slash commands."""
        trie = self._tries.get("command")
        if trie is None:
            return []
        matches = trie.search(prefix.lstrip("/"))
        descs = self._descriptions.get("command", {})
        items = [
            CompletionItem(
                text=f"/{m}",
                category="command",
                score=1.0 if m == prefix.lstrip("/") else 0.8,
                description=descs.get(m, ""),
            )
            for m in matches
        ]
        items.sort(key=lambda c: (-c.score, c.text))
        return items

    def complete_path(self, prefix: str) -> list[CompletionItem]:
        """Complete file paths."""
        trie = self._tries.get("file")
        if trie is None:
            return []
        matches = trie.search(prefix)
        descs = self._descriptions.get("file", {})
        items = [
            CompletionItem(
                text=m,
                category="file",
                score=0.7,
                description=descs.get(m, ""),
            )
            for m in matches
        ]
        items.sort(key=lambda c: c.text)
        return items

    def remove_source(self, category: str) -> None:
        """Remove a completion source."""
        self._tries.pop(category, None)
        self._descriptions.pop(category, None)

    @property
    def sources(self) -> list[str]:
        """List registered source categories."""
        return sorted(self._tries.keys())
