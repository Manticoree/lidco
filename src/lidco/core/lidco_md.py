"""LIDCO.md hierarchical loader — project instructions for agents.

Hierarchy (later layers override earlier):
  1. ~/.lidco/LIDCO.md            (user-level)
  2. LIDCO.md or .lidco/LIDCO.md  (project-level, first found)
  3. /etc/lidco/LIDCO.md          (managed/org-level, Linux)
     C:/ProgramData/lidco/LIDCO.md (managed/org-level, Windows)

Features:
  - @path imports: ``@relative/file.md`` inlines another file (depth limit 3)
  - <!-- scope: glob --> blocks: rules active only for matching files
  - Subdirectory LIDCO.md: lazy-loaded when agent touches files there
"""

from __future__ import annotations

import fnmatch
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_SCOPE_START_RE = re.compile(r"<!--\s*scope:\s*(.+?)\s*-->", re.IGNORECASE)
_SCOPE_END_RE = re.compile(r"<!--\s*end\s*scope\s*-->", re.IGNORECASE)
_IMPORT_RE = re.compile(r"^@(.+)$")
_MAX_IMPORT_DEPTH = 3


@dataclass(frozen=True)
class PathScopedRule:
    """An instruction block that activates only for matching file paths."""

    pattern: str   # glob pattern, e.g. "src/api/**/*.py"
    content: str   # instruction text


@dataclass
class LidcoMdContent:
    """Merged result from all LIDCO.md layers."""

    text: str                                        # main instruction text
    sources: list[str] = field(default_factory=list) # contributing file paths
    scoped_rules: list[PathScopedRule] = field(default_factory=list)


class LidcoMdLoader:
    """Load and merge LIDCO.md files from all hierarchy layers."""

    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir.resolve()
        self._cache: dict[str, LidcoMdContent] = {}
        self._subdir_cache: dict[str, str] = {}  # file_path -> extra instructions

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> LidcoMdContent:
        """Load and merge all LIDCO.md layers. Results are NOT cached (reload on call)."""
        layers: list[tuple[Path, str]] = []  # (source_path, text)

        # Layer 1: user-level
        user_path = Path.home() / ".lidco" / "LIDCO.md"
        self._try_load(user_path, layers)

        # Layer 2: project-level (first found wins)
        for candidate in (
            self._project_dir / ".lidco" / "LIDCO.md",
            self._project_dir / "LIDCO.md",
        ):
            if candidate.exists():
                self._try_load(candidate, layers)
                break

        # Layer 3: managed/org-level
        managed = self._managed_path()
        if managed:
            self._try_load(managed, layers)

        # Merge all layers
        all_text_parts: list[str] = []
        all_sources: list[str] = []
        all_scoped: list[PathScopedRule] = []

        for src_path, raw_text in layers:
            resolved_text, imports_ok = self._resolve_imports(raw_text, src_path.parent, depth=0)
            if not imports_ok:
                logger.debug("Some @imports failed in %s", src_path)
            main_text, scoped = self._extract_scoped_rules(resolved_text)
            all_text_parts.append(main_text.strip())
            all_sources.append(str(src_path))
            all_scoped.extend(scoped)

        merged = "\n\n".join(p for p in all_text_parts if p)
        return LidcoMdContent(text=merged, sources=all_sources, scoped_rules=all_scoped)

    def load_for_path(self, file_path: str) -> str:
        """Return extra instructions from subdirectory LIDCO.md files (lazy, cached)."""
        resolved = Path(file_path).resolve()
        cache_key = str(resolved)
        if cache_key in self._subdir_cache:
            return self._subdir_cache[cache_key]

        extra_parts: list[str] = []
        # Walk from project root to file's directory looking for LIDCO.md
        try:
            rel = resolved.parent.relative_to(self._project_dir)
        except ValueError:
            self._subdir_cache[cache_key] = ""
            return ""

        current = self._project_dir
        for part in rel.parts:
            current = current / part
            candidate = current / "LIDCO.md"
            if candidate.exists() and candidate != self._project_dir / "LIDCO.md":
                try:
                    text = candidate.read_text(encoding="utf-8")
                    main_text, _ = self._extract_scoped_rules(text)
                    extra_parts.append(main_text.strip())
                except OSError:
                    pass

        result = "\n\n".join(p for p in extra_parts if p)
        self._subdir_cache[cache_key] = result
        return result

    def invalidate_subdir_cache(self) -> None:
        self._subdir_cache.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _try_load(self, path: Path, layers: list[tuple[Path, str]]) -> None:
        if not path.exists():
            return
        try:
            text = path.read_text(encoding="utf-8")
            layers.append((path, text))
        except OSError as exc:
            logger.warning("Cannot read %s: %s", path, exc)

    def _resolve_imports(
        self, text: str, base_dir: Path, depth: int
    ) -> tuple[str, bool]:
        """Resolve @path imports recursively. Returns (resolved_text, all_ok)."""
        if depth >= _MAX_IMPORT_DEPTH:
            return text, True

        lines = text.splitlines(keepends=True)
        result_lines: list[str] = []
        all_ok = True

        for line in lines:
            m = _IMPORT_RE.match(line.rstrip())
            if m:
                import_path_str = m.group(1).strip()
                import_path = (base_dir / import_path_str).resolve()
                # Security: only allow imports within project dir or ~/.lidco/
                if not self._is_safe_import(import_path):
                    logger.warning("Blocked unsafe @import: %s", import_path)
                    all_ok = False
                    continue
                try:
                    imported = import_path.read_text(encoding="utf-8")
                    resolved, ok = self._resolve_imports(imported, import_path.parent, depth + 1)
                    if not ok:
                        all_ok = False
                    result_lines.append(resolved)
                except OSError as exc:
                    logger.warning("@import failed for %s: %s", import_path, exc)
                    all_ok = False
            else:
                result_lines.append(line)

        return "".join(result_lines), all_ok

    def _extract_scoped_rules(self, text: str) -> tuple[str, list[PathScopedRule]]:
        """Extract <!-- scope: pattern --> blocks. Returns (main_text, scoped_rules)."""
        scoped: list[PathScopedRule] = []
        lines = text.splitlines(keepends=True)
        result_lines: list[str] = []
        in_scope = False
        current_pattern = ""
        current_lines: list[str] = []

        for line in lines:
            start_m = _SCOPE_START_RE.search(line)
            end_m = _SCOPE_END_RE.search(line)

            if start_m and not in_scope:
                in_scope = True
                current_pattern = start_m.group(1)
                current_lines = []
            elif end_m and in_scope:
                scoped.append(PathScopedRule(
                    pattern=current_pattern,
                    content="".join(current_lines).strip(),
                ))
                in_scope = False
                current_pattern = ""
                current_lines = []
            elif in_scope:
                current_lines.append(line)
            else:
                result_lines.append(line)

        return "".join(result_lines), scoped

    def _is_safe_import(self, path: Path) -> bool:
        """Only allow imports under project dir or ~/.lidco/."""
        try:
            path.relative_to(self._project_dir)
            return True
        except ValueError:
            pass
        try:
            path.relative_to(Path.home() / ".lidco")
            return True
        except ValueError:
            pass
        return False

    @staticmethod
    def _managed_path() -> Path | None:
        if sys.platform == "win32":
            return Path("C:/ProgramData/lidco/LIDCO.md")
        return Path("/etc/lidco/LIDCO.md")


class RuleActivator:
    """Activate path-scoped rules based on current files being edited."""

    @staticmethod
    def get_active_rules(
        scoped_rules: list[PathScopedRule],
        current_files: list[str],
    ) -> list[str]:
        """Return instruction texts whose scope patterns match any current file."""
        if not scoped_rules or not current_files:
            return []
        active: list[str] = []
        for rule in scoped_rules:
            if any(RuleActivator._file_matches(f, rule.pattern) for f in current_files):
                active.append(rule.content)
        return active

    @staticmethod
    def _file_matches(file_path: str, pattern: str) -> bool:
        """Match file path against a glob pattern supporting ** for any depth.

        ** matches zero or more path segments (including none).
        * matches any chars within a single segment.
        """
        fp = file_path.replace("\\", "/")
        pat = pattern.replace("\\", "/")

        # Build regex character by character
        regex = ""
        i = 0
        while i < len(pat):
            if pat[i : i + 2] == "**":
                regex += ".*"
                i += 2
                # Consume trailing "/" after ** (becomes optional separator)
                if i < len(pat) and pat[i] == "/":
                    regex += "/?"
                    i += 1
            elif pat[i] == "*":
                regex += "[^/]*"
                i += 1
            elif pat[i] in r"\.+^${}[]|()?":
                regex += re.escape(pat[i])
                i += 1
            else:
                regex += pat[i]
                i += 1

        return bool(re.search(r"(?:^|/)" + regex + r"$", fp))
