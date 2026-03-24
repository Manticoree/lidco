"""Gitignore-style context exclusion via .lidcoignore files."""

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExcludePattern:
    """A single parsed exclusion pattern."""

    pattern: str
    source: str  # file path where defined
    negated: bool  # True if line starts with !


@dataclass
class ExcludeResult:
    """Result of checking whether a path is excluded."""

    excluded: bool
    matched_pattern: str  # empty if not excluded


class ContextExcludeFile:
    """Reads .lidcoignore (or .lidco/ignore) and checks paths against patterns.

    Supports gitignore-style syntax:
    - Glob patterns (*.pyc, build/, **/node_modules/**)
    - Comments (lines starting with #)
    - Negation (lines starting with ! re-include previously excluded paths)
    - Directory patterns (trailing / matches contents)
    - Mtime-based cache invalidation for live reloads
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root)
        self._mtime: float = 0.0
        self._patterns: list[ExcludePattern] = []

    def _find_exclude_file(self) -> Path | None:
        """Try .lidcoignore first, then .lidco/ignore."""
        primary = self.project_root / ".lidcoignore"
        if primary.exists():
            return primary
        secondary = self.project_root / ".lidco" / "ignore"
        if secondary.exists():
            return secondary
        return None

    def load(self) -> list[ExcludePattern]:
        """Read exclude file, parse gitignore syntax.

        Lines starting with # are comments; blank lines skipped.
        Lines starting with ! are negation patterns.
        """
        path = self._find_exclude_file()
        if not path:
            self._patterns = []
            return []
        try:
            mtime = path.stat().st_mtime
            content = path.read_text(encoding="utf-8")
        except OSError:
            self._patterns = []
            return []
        patterns: list[ExcludePattern] = []
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            negated = stripped.startswith("!")
            pat = stripped[1:] if negated else stripped
            patterns.append(
                ExcludePattern(pattern=pat, source=str(path), negated=negated)
            )
        self._mtime = mtime
        self._patterns = patterns
        return list(patterns)

    def _get_patterns(self) -> list[ExcludePattern]:
        """Load with mtime-based cache invalidation."""
        path = self._find_exclude_file()
        if not path:
            return []
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return []
        if mtime != self._mtime:
            self.load()
        return self._patterns

    def _match(self, pattern: str, path: str) -> bool:
        """Match a path against a gitignore-style pattern.

        Directory patterns (trailing /) match files inside that dir.
        """
        # Normalize to forward slashes
        path = path.replace("\\", "/").lstrip("/")

        if pattern.endswith("/"):
            # Directory pattern: match dir itself and files inside
            dir_pat = pattern.rstrip("/")
            return fnmatch.fnmatch(path, dir_pat + "/*") or fnmatch.fnmatch(
                path, dir_pat
            )

        # ** matches any path segment
        if "**" in pattern:
            regex_pat = pattern.replace("**", "*")
            return fnmatch.fnmatch(path, regex_pat) or fnmatch.fnmatch(
                path.split("/")[-1], pattern.split("/")[-1]
            )

        # Match against full path and basename
        return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(
            path.split("/")[-1], pattern
        )

    def is_excluded(self, file_path: str) -> ExcludeResult:
        """Check if file_path is excluded. Negation patterns can re-include."""
        patterns = self._get_patterns()

        # Make path relative to project root
        try:
            rel = str(
                Path(file_path).resolve().relative_to(self.project_root.resolve())
            )
        except ValueError:
            rel = str(file_path)
        rel = rel.replace("\\", "/")

        excluded = False
        matched = ""
        for ep in patterns:
            if self._match(ep.pattern, rel):
                if ep.negated:
                    excluded = False
                    matched = ""
                else:
                    excluded = True
                    matched = ep.pattern
        return ExcludeResult(excluded=excluded, matched_pattern=matched)

    def filter_paths(self, paths: list[str]) -> list[str]:
        """Return only non-excluded paths."""
        return [p for p in paths if not self.is_excluded(p).excluded]

    def add_pattern(self, pattern: str) -> None:
        """Append pattern to the exclude file."""
        path = self._find_exclude_file()
        if not path:
            path = self.project_root / ".lidcoignore"
        try:
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            sep = "\n" if existing and not existing.endswith("\n") else ""
            path.write_text(existing + sep + pattern + "\n", encoding="utf-8")
            self._mtime = 0.0  # invalidate cache
        except OSError:
            pass

    def remove_pattern(self, pattern: str) -> bool:
        """Remove pattern line from exclude file. Returns True if found."""
        path = self._find_exclude_file()
        if not path or not path.exists():
            return False
        try:
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            new_lines = [
                line
                for line in lines
                if line.strip().lstrip("!") != pattern.lstrip("!")
            ]
            if len(new_lines) == len(lines):
                return False
            path.write_text("".join(new_lines), encoding="utf-8")
            self._mtime = 0.0  # invalidate cache
            return True
        except OSError:
            return False

    def list_patterns(self) -> list[ExcludePattern]:
        """Return current patterns (loading/reloading as needed)."""
        return self._get_patterns()
