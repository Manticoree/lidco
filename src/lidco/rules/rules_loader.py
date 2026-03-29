"""RulesFileLoader — load .md rule files with frontmatter glob patterns.

Task 727: Q119.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


@dataclass
class RulesFile:
    """A single rules file with its glob pattern and content."""

    path: str
    glob_pattern: str
    content: str
    mtime: float = 0.0


class RulesFileLoader:
    """Load and cache rules files from a directory.

    Parameters
    ----------
    rules_dir:
        Path to the directory containing ``*.md`` rule files.
    read_fn:
        ``read_fn(path) -> str`` — reads file content.  Falls back to
        stdlib ``open`` when *None*.
    listdir_fn:
        ``listdir_fn(dir) -> list[str]`` — lists filenames.  Falls back
        to ``os.listdir``.
    mtime_fn:
        ``mtime_fn(path) -> float`` — returns file modification time.
        Falls back to ``os.path.getmtime``.
    """

    def __init__(
        self,
        rules_dir: str = ".lidco/rules",
        read_fn=None,
        listdir_fn=None,
        mtime_fn=None,
    ) -> None:
        self._rules_dir = rules_dir
        self._read_fn = read_fn or self._default_read
        self._listdir_fn = listdir_fn or os.listdir
        self._mtime_fn = mtime_fn or os.path.getmtime
        self._cache: dict[str, RulesFile] = {}

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def load_all(self) -> list[RulesFile]:
        """Load all ``*.md`` files in *rules_dir*, returning cached entries
        when the file has not changed (same *mtime*)."""
        try:
            filenames = self._listdir_fn(self._rules_dir)
        except (OSError, FileNotFoundError):
            return []

        md_files = [f for f in filenames if f.endswith(".md")]
        current_paths: set[str] = set()
        result: list[RulesFile] = []

        for name in md_files:
            path = os.path.join(self._rules_dir, name)
            current_paths.add(path)

            try:
                mtime = self._mtime_fn(path)
            except (OSError, FileNotFoundError):
                continue

            cached = self._cache.get(path)
            if cached is not None and cached.mtime == mtime:
                result.append(cached)
                continue

            try:
                raw = self._read_fn(path)
            except (OSError, FileNotFoundError):
                continue

            glob_pattern, body = self._parse_frontmatter(raw)
            entry = RulesFile(path=path, glob_pattern=glob_pattern, content=body, mtime=mtime)
            self._cache[path] = entry
            result.append(entry)

        # Evict removed files from cache.
        stale = set(self._cache) - current_paths
        for key in stale:
            del self._cache[key]

        return result

    def clear_cache(self) -> None:
        """Drop all cached entries so the next ``load_all`` re-reads."""
        self._cache.clear()

    # ------------------------------------------------------------------ #
    # Frontmatter parsing                                                 #
    # ------------------------------------------------------------------ #

    def _parse_frontmatter(self, content: str) -> tuple[str, str]:
        """Return ``(glob_pattern, body)`` extracted from YAML-style
        frontmatter.

        Frontmatter format::

            ---
            globs: "**/*.py"
            ---
            body text ...

        If no frontmatter or no ``globs:`` field, returns ``("*", content)``.
        Quotes (single or double) around the glob value are stripped.
        """
        if not content.startswith("---"):
            return ("*", content)

        lines = content.split("\n")
        # Find closing '---' (must be after the first line).
        closing_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                closing_idx = i
                break

        if closing_idx is None:
            return ("*", content)

        frontmatter_lines = lines[1:closing_idx]
        body = "\n".join(lines[closing_idx + 1:]).lstrip("\n")

        glob_pattern = "*"
        for line in frontmatter_lines:
            stripped = line.strip()
            if stripped.lower().startswith("globs:"):
                value = stripped[len("globs:"):].strip()
                # Strip surrounding quotes.
                if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                glob_pattern = value
                break

        return (glob_pattern, body)

    # ------------------------------------------------------------------ #
    # Default I/O helpers                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _default_read(path: str) -> str:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
