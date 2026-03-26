"""
TODO/FIXME Scanner — tech debt tracker.

Scans source files for annotation comments (TODO, FIXME, HACK, XXX, BUG,
OPTIMIZE, NOTE, REVIEW) and produces a structured report.

Optionally uses `git blame` to associate each item with its author.

Supports all text-based source files.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Tag definitions
# ---------------------------------------------------------------------------

# Tag → severity
TAG_SEVERITY: dict[str, str] = {
    "FIXME":    "high",
    "BUG":      "high",
    "HACK":     "high",
    "XXX":      "high",
    "TODO":     "medium",
    "OPTIMIZE": "low",
    "REVIEW":   "low",
    "NOTE":     "info",
    "NOSONAR":  "info",
}

ALL_TAGS = tuple(TAG_SEVERITY.keys())

# Regex: matches "# TODO(author): text" or "// FIXME: text" or "<!-- NOTE text -->"
_TAG_RE = re.compile(
    r"(?://|#|<!--|--)\s*"
    r"(?P<tag>" + "|".join(ALL_TAGS) + r")"
    r"(?:\((?P<owner>[^)]*)\))?"    # optional (author)
    r"[:\s]\s*"
    r"(?P<text>.+?)(?:\s*-->)?\s*$",
    re.IGNORECASE,
)

_SKIP_DIRS = frozenset({
    ".git", "__pycache__", ".mypy_cache", ".pytest_cache",
    "node_modules", ".venv", "venv", "dist", "build",
})

_TEXT_EXTENSIONS = frozenset({
    ".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java",
    ".c", ".h", ".cpp", ".cc", ".hpp", ".cs", ".rb", ".php",
    ".swift", ".kt", ".scala", ".sh", ".bash", ".html", ".htm",
    ".css", ".scss", ".yaml", ".yml", ".toml", ".sql", ".lua",
    ".ex", ".exs", ".dart", ".tf", ".proto", ".r",
})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TodoItem:
    file: str
    line: int
    tag: str          # "TODO", "FIXME", etc.
    severity: str     # "high" | "medium" | "low" | "info"
    text: str         # the annotation text
    owner: str = ""   # from (owner) syntax or git blame
    context: str = "" # surrounding code line (stripped)


@dataclass
class TodoReport:
    items: list[TodoItem]
    files_scanned: int
    by_tag: dict[str, list[TodoItem]] = field(default_factory=dict)
    by_file: dict[str, list[TodoItem]] = field(default_factory=dict)

    def __post_init__(self):
        for item in self.items:
            self.by_tag.setdefault(item.tag, []).append(item)
            self.by_file.setdefault(item.file, []).append(item)

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.items if i.severity == "high")

    @property
    def medium_count(self) -> int:
        return sum(1 for i in self.items if i.severity == "medium")

    def summary(self) -> str:
        return (
            f"{len(self.items)} items in {len(self.by_file)} files | "
            f"{self.high_count} high | {self.medium_count} medium"
        )


# ---------------------------------------------------------------------------
# Git blame helper
# ---------------------------------------------------------------------------

def _blame_author(filepath: str, lineno: int, cwd: str) -> str:
    """Return the git blame author for a specific line (empty on failure)."""
    try:
        proc = subprocess.run(
            ["git", "blame", "-L", f"{lineno},{lineno}", "--porcelain", filepath],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=5,
        )
        for line in proc.stdout.splitlines():
            if line.startswith("author "):
                return line[7:].strip()
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# TodoScanner
# ---------------------------------------------------------------------------

class TodoScanner:
    """
    Scan source files for TODO/FIXME/HACK/etc. annotations.

    Parameters
    ----------
    project_root : str | None
        Root directory to scan.
    tags : tuple[str, ...] | None
        Tags to look for. Defaults to ALL_TAGS.
    use_git_blame : bool
        Try to attribute each item to its git author. Slower but richer.
    max_file_size_kb : int
        Skip files larger than this limit.
    """

    def __init__(
        self,
        project_root: str | None = None,
        tags: tuple[str, ...] | None = None,
        use_git_blame: bool = False,
        max_file_size_kb: int = 256,
    ) -> None:
        self._root = Path(project_root) if project_root else Path.cwd()
        self._tags = frozenset(t.upper() for t in (tags or ALL_TAGS))
        self._use_git_blame = use_git_blame
        self._max_bytes = max_file_size_kb * 1024

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self) -> TodoReport:
        items: list[TodoItem] = []
        files_scanned = 0

        for path in self._iter_files():
            try:
                if path.stat().st_size > self._max_bytes:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            files_scanned += 1
            file_items = self._scan_file(path, text)
            items.extend(file_items)

        return TodoReport(items=items, files_scanned=files_scanned)

    def scan_file(self, filepath: str) -> list[TodoItem]:
        """Scan a single file and return its TodoItems."""
        path = Path(filepath)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []
        return self._scan_file(path, text)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _iter_files(self):
        import os
        for dirpath, dirnames, filenames in os.walk(self._root):
            dirnames[:] = [
                d for d in dirnames
                if d not in _SKIP_DIRS and not d.startswith(".")
            ]
            for fname in filenames:
                p = Path(dirpath) / fname
                if p.suffix.lower() in _TEXT_EXTENSIONS:
                    yield p

    def _scan_file(self, path: Path, text: str) -> list[TodoItem]:
        items: list[TodoItem] = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = _TAG_RE.search(line)
            if not m:
                continue
            tag = m.group("tag").upper()
            if tag not in self._tags:
                continue

            owner = (m.group("owner") or "").strip()
            if not owner and self._use_git_blame:
                owner = _blame_author(str(path), lineno, str(self._root))

            items.append(TodoItem(
                file=str(path),
                line=lineno,
                tag=tag,
                severity=TAG_SEVERITY.get(tag, "info"),
                text=m.group("text").strip(),
                owner=owner,
                context=line.strip(),
            ))
        return items
