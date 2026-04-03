"""Polyglot symbol search with name normalization."""
from __future__ import annotations

import re
from dataclasses import dataclass

from lidco.polyglot.parser import Symbol


class PolyglotSearch:
    """Search symbols across languages with name normalization."""

    def __init__(self) -> None:
        self._symbols: list[Symbol] = []

    def add_symbols(self, symbols: list[Symbol]) -> None:
        """Add symbols to the search index (immutable append)."""
        self._symbols = [*self._symbols, *symbols]

    def search(self, query: str, language: str | None = None) -> list[Symbol]:
        """Search symbols by name, optionally filtering by language."""
        normalized = self.normalize_name(query)
        results: list[Symbol] = []
        for sym in self._symbols:
            if language is not None and sym.language != language:
                continue
            if normalized in self.normalize_name(sym.name):
                results.append(sym)
        return results

    def search_by_kind(self, kind: str) -> list[Symbol]:
        """Search symbols by kind (function, class, etc.)."""
        return [s for s in self._symbols if s.kind == kind]

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize snake_case / camelCase to a common lowercase form.

        ``getUserName`` and ``get_user_name`` both become ``getusername``.
        """
        # Insert underscore before uppercase runs then lowercase everything
        s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
        s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
        return s.replace("_", "").replace("-", "").lower()

    def stats(self) -> dict[str, int]:
        """Return symbol counts grouped by language."""
        counts: dict[str, int] = {}
        for sym in self._symbols:
            counts[sym.language] = counts.get(sym.language, 0) + 1
        return counts
