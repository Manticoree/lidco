"""
Code Statistics — cloc/tokei-style language breakdown.

Counts lines of code (LOC), blank lines, and comment lines per file/language.
Pure stdlib, no external dependencies. Fast recursive walk.

Supported languages (extensible via LANGUAGE_MAP):
  Python, JavaScript, TypeScript, Rust, Go, Java, C/C++, C#,
  Ruby, PHP, Swift, Kotlin, Scala, Shell, HTML, CSS, YAML, JSON,
  TOML, Markdown, SQL, and more.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Language definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LanguageDef:
    name: str
    single_line_comment: tuple[str, ...]   # e.g. ("#",)
    block_comment_start: str = ""          # e.g. "/*"
    block_comment_end: str = ""            # e.g. "*/"
    string_block: tuple[str, ...] = ()     # e.g. ('"""', "'''") for Python


# Extension → LanguageDef
LANGUAGE_MAP: dict[str, LanguageDef] = {
    ".py":    LanguageDef("Python",     ("#",),         '"""', '"""', ('"""', "'''")),
    ".pyi":   LanguageDef("Python",     ("#",),         '"""', '"""', ('"""', "'''")),
    ".js":    LanguageDef("JavaScript", ("//",),        "/*",  "*/"),
    ".mjs":   LanguageDef("JavaScript", ("//",),        "/*",  "*/"),
    ".jsx":   LanguageDef("JavaScript", ("//",),        "/*",  "*/"),
    ".ts":    LanguageDef("TypeScript", ("//",),        "/*",  "*/"),
    ".tsx":   LanguageDef("TypeScript", ("//",),        "/*",  "*/"),
    ".rs":    LanguageDef("Rust",       ("//",),        "/*",  "*/"),
    ".go":    LanguageDef("Go",         ("//",),        "/*",  "*/"),
    ".java":  LanguageDef("Java",       ("//",),        "/*",  "*/"),
    ".c":     LanguageDef("C",          ("//",),        "/*",  "*/"),
    ".h":     LanguageDef("C",          ("//",),        "/*",  "*/"),
    ".cpp":   LanguageDef("C++",        ("//",),        "/*",  "*/"),
    ".cc":    LanguageDef("C++",        ("//",),        "/*",  "*/"),
    ".hpp":   LanguageDef("C++",        ("//",),        "/*",  "*/"),
    ".cs":    LanguageDef("C#",         ("//",),        "/*",  "*/"),
    ".rb":    LanguageDef("Ruby",       ("#",),         "=begin", "=end"),
    ".php":   LanguageDef("PHP",        ("//", "#"),    "/*",  "*/"),
    ".swift": LanguageDef("Swift",      ("//",),        "/*",  "*/"),
    ".kt":    LanguageDef("Kotlin",     ("//",),        "/*",  "*/"),
    ".scala": LanguageDef("Scala",      ("//",),        "/*",  "*/"),
    ".sh":    LanguageDef("Shell",      ("#",)),
    ".bash":  LanguageDef("Shell",      ("#",)),
    ".zsh":   LanguageDef("Shell",      ("#",)),
    ".html":  LanguageDef("HTML",       (),             "<!--", "-->"),
    ".htm":   LanguageDef("HTML",       (),             "<!--", "-->"),
    ".css":   LanguageDef("CSS",        (),             "/*",   "*/"),
    ".scss":  LanguageDef("SCSS",       ("//",),        "/*",   "*/"),
    ".yaml":  LanguageDef("YAML",       ("#",)),
    ".yml":   LanguageDef("YAML",       ("#",)),
    ".json":  LanguageDef("JSON",       ()),
    ".toml":  LanguageDef("TOML",       ("#",)),
    ".md":    LanguageDef("Markdown",   ()),
    ".sql":   LanguageDef("SQL",        ("--",),        "/*",  "*/"),
    ".lua":   LanguageDef("Lua",        ("--",),        "--[[", "]]"),
    ".r":     LanguageDef("R",          ("#",)),
    ".jl":    LanguageDef("Julia",      ("#",),         "#=",  "=#"),
    ".ex":    LanguageDef("Elixir",     ("#",)),
    ".exs":   LanguageDef("Elixir",     ("#",)),
    ".tf":    LanguageDef("Terraform",  ("#", "//"),    "/*",  "*/"),
    ".proto": LanguageDef("Protobuf",   ("//",),        "/*",  "*/"),
    ".dart":  LanguageDef("Dart",       ("//",),        "/*",  "*/"),
}

# Directories to always skip
_SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".tox", ".venv", "venv", "env", "node_modules", ".node_modules",
    "dist", "build", ".build", "target", ".cache", ".idea", ".vscode",
    "vendor", "third_party", ".eggs", "*.egg-info",
})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FileStat:
    path: str
    language: str
    total_lines: int
    code_lines: int
    comment_lines: int
    blank_lines: int


@dataclass
class LanguageStat:
    language: str
    files: int = 0
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0


@dataclass
class CodeStatsReport:
    by_language: dict[str, LanguageStat]
    file_stats: list[FileStat]
    total_files: int
    total_lines: int
    total_code: int
    total_comments: int
    total_blank: int
    skipped_files: int = 0

    def top_languages(self, n: int = 5) -> list[LanguageStat]:
        return sorted(
            self.by_language.values(), key=lambda s: s.code_lines, reverse=True
        )[:n]

    def summary(self) -> str:
        top = ", ".join(
            f"{s.language} ({s.code_lines:,} loc)"
            for s in self.top_languages(3)
        )
        return (
            f"{self.total_files} files | "
            f"{self.total_code:,} LOC | "
            f"{self.total_comments:,} comments | "
            f"{self.total_blank:,} blank"
            + (f" | top: {top}" if top else "")
        )


# ---------------------------------------------------------------------------
# Line counter
# ---------------------------------------------------------------------------

def _count_lines(text: str, lang: LanguageDef) -> tuple[int, int, int]:
    """Return (code_lines, comment_lines, blank_lines)."""
    code = blank = comment = 0
    in_block = False

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            blank += 1
            continue

        if in_block:
            comment += 1
            if lang.block_comment_end and lang.block_comment_end in line:
                in_block = False
            continue

        # Block comment start
        if lang.block_comment_start and line.startswith(lang.block_comment_start):
            comment += 1
            if lang.block_comment_end and lang.block_comment_end not in line[len(lang.block_comment_start):]:
                in_block = True
            continue

        # Single-line comment
        is_comment = any(line.startswith(prefix) for prefix in lang.single_line_comment)
        if is_comment:
            comment += 1
        else:
            code += 1

    return code, comment, blank


# ---------------------------------------------------------------------------
# CodeStats
# ---------------------------------------------------------------------------

class CodeStats:
    """
    Walk a project directory and compute code statistics per language.

    Parameters
    ----------
    project_root : str | None
        Root directory. Defaults to cwd.
    include_hidden : bool
        Include hidden files/dirs (starting with dot). Default False.
    max_file_size_kb : int
        Skip files larger than this. Default 512 KB.
    """

    def __init__(
        self,
        project_root: str | None = None,
        include_hidden: bool = False,
        max_file_size_kb: int = 512,
    ) -> None:
        self._root = Path(project_root) if project_root else Path.cwd()
        self._include_hidden = include_hidden
        self._max_bytes = max_file_size_kb * 1024

    def analyze(self) -> CodeStatsReport:
        file_stats: list[FileStat] = []
        by_language: dict[str, LanguageStat] = {}
        skipped = 0

        for path in self._walk():
            ext = path.suffix.lower()
            lang_def = LANGUAGE_MAP.get(ext)
            if lang_def is None:
                continue

            try:
                size = path.stat().st_size
                if size > self._max_bytes:
                    skipped += 1
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                skipped += 1
                continue

            lines = text.splitlines()
            total = len(lines)
            code, comment, blank = _count_lines(text, lang_def)

            fstat = FileStat(
                path=str(path),
                language=lang_def.name,
                total_lines=total,
                code_lines=code,
                comment_lines=comment,
                blank_lines=blank,
            )
            file_stats.append(fstat)

            ls = by_language.setdefault(
                lang_def.name,
                LanguageStat(language=lang_def.name),
            )
            ls.files += 1
            ls.total_lines += total
            ls.code_lines += code
            ls.comment_lines += comment
            ls.blank_lines += blank

        total_files = len(file_stats)
        return CodeStatsReport(
            by_language=by_language,
            file_stats=file_stats,
            total_files=total_files,
            total_lines=sum(f.total_lines for f in file_stats),
            total_code=sum(f.code_lines for f in file_stats),
            total_comments=sum(f.comment_lines for f in file_stats),
            total_blank=sum(f.blank_lines for f in file_stats),
            skipped_files=skipped,
        )

    def _walk(self):
        for dirpath, dirnames, filenames in os.walk(self._root):
            # Prune skipped dirs in-place
            dirnames[:] = [
                d for d in dirnames
                if d not in _SKIP_DIRS
                and (self._include_hidden or not d.startswith("."))
            ]
            for fname in filenames:
                if not self._include_hidden and fname.startswith("."):
                    continue
                yield Path(dirpath) / fname
