"""Snippet Manager — save, search, and expand reusable code snippets (stdlib only).

Like VS Code's user snippets: named templates with ${variable} placeholders
that expand to full code blocks.  Backed by a JSON file in .lidco/snippets/.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class SnippetError(Exception):
    """Raised when a snippet operation fails."""


@dataclass
class Snippet:
    """A reusable code snippet with optional variable placeholders."""

    name: str
    body: str
    description: str = ""
    language: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Variable syntax: ${VAR_NAME} or ${VAR_NAME:default_value}
    _VAR_RE = re.compile(r"\$\{(\w+)(?::([^}]*))?\}")

    def variables(self) -> list[str]:
        """Return list of variable names in the snippet body."""
        return [m.group(1) for m in self._VAR_RE.finditer(self.body)]

    def expand(self, bindings: dict[str, str] | None = None) -> str:
        """Expand snippet, substituting variables with *bindings* or defaults."""
        bindings = bindings or {}

        def replace(m: re.Match) -> str:
            var_name = m.group(1)
            default = m.group(2) or ""
            return bindings.get(var_name, default)

        return self._VAR_RE.sub(replace, self.body)

    def matches_query(self, query: str) -> bool:
        """True if name, description, or tags contain *query* (case-insensitive)."""
        q = query.lower()
        return (
            q in self.name.lower()
            or q in self.description.lower()
            or any(q in t.lower() for t in self.tags)
        )

    def word_count(self) -> int:
        return len(self.body.split())


class SnippetStore:
    """File-backed store for code snippets.

    Snippets are persisted as a JSON array in *base_dir/snippets.json*.

    Usage::

        store = SnippetStore()
        store.save(Snippet("logger", 'import logging\\nlog = logging.getLogger("${NAME}")'))
        snippet = store.get("logger")
        code = snippet.expand({"NAME": "myapp"})
    """

    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            base_dir = Path(".lidco") / "snippets"
        self._dir = Path(base_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "snippets.json"
        self._cache: dict[str, Snippet] | None = None

    # ------------------------------------------------------------------ #
    # Persistence helpers                                                  #
    # ------------------------------------------------------------------ #

    def _load(self) -> dict[str, Snippet]:
        if self._cache is not None:
            return self._cache
        if not self._file.exists():
            self._cache = {}
            return self._cache
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            self._cache = {
                item["name"]: Snippet(**{k: v for k, v in item.items()})
                for item in data
            }
        except (json.JSONDecodeError, KeyError):
            self._cache = {}
        return self._cache

    def _save(self) -> None:
        snippets = list(self._load().values())
        data = [asdict(s) for s in snippets]
        self._file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _invalidate(self) -> None:
        self._cache = None

    # ------------------------------------------------------------------ #
    # CRUD                                                                 #
    # ------------------------------------------------------------------ #

    def save(self, snippet: Snippet) -> None:
        """Create or update a snippet."""
        if not snippet.name.strip():
            raise SnippetError("Snippet name must not be empty")
        store = self._load()
        snippet.updated_at = time.time()
        store[snippet.name] = snippet
        self._save()

    def get(self, name: str) -> Snippet | None:
        return self._load().get(name)

    def delete(self, name: str) -> bool:
        """Delete snippet by name. Returns True if it existed."""
        store = self._load()
        if name not in store:
            return False
        del store[name]
        self._save()
        return True

    def list_all(self, language: str | None = None) -> list[Snippet]:
        snippets = list(self._load().values())
        if language:
            snippets = [s for s in snippets if s.language == language]
        return sorted(snippets, key=lambda s: s.name)

    def __len__(self) -> int:
        return len(self._load())

    # ------------------------------------------------------------------ #
    # Search                                                               #
    # ------------------------------------------------------------------ #

    def search(
        self,
        query: str,
        language: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Snippet]:
        results = [s for s in self._load().values() if s.matches_query(query)]
        if language:
            results = [s for s in results if s.language == language]
        if tags:
            tag_set = set(tags)
            results = [s for s in results if tag_set & set(s.tags)]
        return sorted(results, key=lambda s: s.name)

    def find_by_tag(self, tag: str) -> list[Snippet]:
        return [s for s in self._load().values() if tag in s.tags]

    # ------------------------------------------------------------------ #
    # Expansion                                                            #
    # ------------------------------------------------------------------ #

    def expand(self, name: str, bindings: dict[str, str] | None = None) -> str:
        """Expand a snippet by name."""
        snippet = self.get(name)
        if snippet is None:
            raise SnippetError(f"Snippet not found: {name!r}")
        return snippet.expand(bindings)
