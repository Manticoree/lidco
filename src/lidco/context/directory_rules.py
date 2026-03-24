"""Per-directory AI rules resolver (T582).

Walks from a file path upward to the project root, collecting `.lidco-rules`
files at each directory level.  Nearest rules have highest priority (appear
last in merged output) so they can override ancestor defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DirectoryRule:
    """A single rule file discovered in a directory."""

    path: str  # directory where this rule file lives
    content: str  # raw text content of the rule file
    priority: int  # lower number = further from file (lower priority)
    source_file: str  # full path to the .lidco-rules file


@dataclass
class RulesCache:
    """Simple mtime-based cache for rule files."""

    _cache: dict = field(default_factory=dict)  # {str(path): (mtime, content)}

    def get(self, path: Path) -> Optional[str]:
        """Return cached content if mtime unchanged, else None."""
        key = str(path)
        if key not in self._cache:
            return None
        try:
            current_mtime = path.stat().st_mtime
        except OSError:
            # File deleted or inaccessible -> cache miss
            self._cache.pop(key, None)
            return None
        cached_mtime, cached_content = self._cache[key]
        if current_mtime == cached_mtime:
            return cached_content
        # mtime changed -> invalidate
        self._cache.pop(key, None)
        return None

    def set(self, path: Path, content: str) -> None:
        """Cache content with current mtime."""
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        self._cache[str(path)] = (mtime, content)


class DirectoryRulesResolver:
    """Resolve per-directory AI rule files by walking up to project root."""

    def __init__(self, project_root: Path, filename: str = ".lidco-rules") -> None:
        self.project_root = project_root.resolve()
        self.filename = filename
        self._cache = RulesCache()

    def _read_rule_file(self, path: Path) -> Optional[str]:
        """Read a rule file, using cache when possible. Returns None on error or empty."""
        cached = self._cache.get(path)
        if cached is not None:
            return cached
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, PermissionError):
            return None
        if not content.strip():
            return None
        self._cache.set(path, content)
        return content

    def resolve(self, file_path: Path) -> list[DirectoryRule]:
        """Walk from file_path up to project_root, collect all rule files.

        Returns list ordered by priority (furthest ancestor = lowest priority first,
        nearest directory = highest priority last).
        """
        file_path = Path(file_path).resolve()
        # Start from the parent directory of the file
        current = file_path.parent if not file_path.is_dir() else file_path
        current = current.resolve()

        collected: list[tuple[Path, str]] = []

        while True:
            # Only consider directories at or below project root
            try:
                current.relative_to(self.project_root)
            except ValueError:
                break

            rule_file = current / self.filename
            content = self._read_rule_file(rule_file)
            if content is not None:
                collected.append((current, content))

            if current == self.project_root:
                break
            parent = current.parent.resolve()
            if parent == current:
                break
            current = parent

        # collected is from file toward root -> reverse so root is first (lowest priority)
        collected.reverse()

        return [
            DirectoryRule(
                path=str(directory),
                content=content,
                priority=idx,
                source_file=str(directory / self.filename),
            )
            for idx, (directory, content) in enumerate(collected)
        ]

    def resolve_merged(self, file_path: Path) -> str:
        """Return all rules merged with section headers.

        Nearest directory rules appear last (highest priority / override).
        Sections separated by ``--- Rules from {dir} ---`` headers.
        """
        rules = self.resolve(file_path)
        if not rules:
            return ""
        sections: list[str] = []
        for rule in rules:
            sections.append(f"--- Rules from {rule.path} ---")
            sections.append(rule.content)
        return "\n".join(sections)

    def find_all_rules(self) -> list[DirectoryRule]:
        """Scan entire project tree for rule files. Returns all found."""
        results: list[DirectoryRule] = []
        for rule_path in sorted(self.project_root.rglob(self.filename)):
            content = self._read_rule_file(rule_path)
            if content is None:
                continue
            directory = rule_path.parent
            results.append(
                DirectoryRule(
                    path=str(directory),
                    content=content,
                    priority=0,  # flat scan, no relative priority
                    source_file=str(rule_path),
                )
            )
        return results

    def inject_for_context(self, file_paths: list[str]) -> str:
        """Resolve rules for multiple files, deduplicate, return injection text.

        Rules from the same source file are included only once.
        Prefix with ``## AI Rules\\n``.
        """
        if not file_paths:
            return ""

        seen_sources: set[str] = set()
        ordered_rules: list[DirectoryRule] = []

        for fp in file_paths:
            rules = self.resolve(Path(fp))
            for rule in rules:
                if rule.source_file not in seen_sources:
                    seen_sources.add(rule.source_file)
                    ordered_rules.append(rule)

        if not ordered_rules:
            return ""

        sections: list[str] = ["## AI Rules"]
        for rule in ordered_rules:
            sections.append(f"--- Rules from {rule.path} ---")
            sections.append(rule.content)
        return "\n".join(sections)
