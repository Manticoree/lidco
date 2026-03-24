"""File-watch mode — detects # LIDCO: annotations and triggers the agent.

Usage:
    lidco watch [PATH]

When a file containing a `# LIDCO: <instruction>` (or `// LIDCO:`) comment is
saved, the watcher extracts the instruction, runs it through the agent headlessly,
writes the result, then removes the annotation from the source file.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# Patterns: `# LIDCO: do X` or `// LIDCO: do X`
_ANNOTATION_RE = re.compile(
    r"^\s*(?:#|//)\s*LIDCO:\s*(.+)$",
    re.IGNORECASE,
)
# Multi-line block start: `# LIDCO: |`
_BLOCK_START_RE = re.compile(
    r"^\s*(?:#|//)\s*LIDCO:\s*\|\s*$",
    re.IGNORECASE,
)
# Comment continuation line (for multi-line blocks)
_COMMENT_LINE_RE = re.compile(r"^\s*(?:#|//)\s*(.*)")

# Directories to skip
_SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "node_modules", "__pycache__",
    ".venv", "venv", ".mypy_cache", ".pytest_cache", "dist", "build",
})


@dataclass
class Annotation:
    file_path: str
    line_number: int      # 1-based
    instruction: str
    context_lines: list[str] = field(default_factory=list)


class FileWatcher:
    """Watches a directory tree for LIDCO annotation comments."""

    def __init__(
        self,
        watch_path: str | Path | None = None,
        debounce_ms: int = 500,
    ) -> None:
        self._watch_path = Path(watch_path) if watch_path else Path.cwd()
        self._debounce_ms = debounce_ms
        self._mtimes: dict[str, float] = {}
        self._running = False
        self._on_annotation: Callable[[Annotation], None] | None = None

    def set_annotation_handler(self, handler: Callable[[Annotation], None]) -> None:
        """Register callback invoked when an annotation is found."""
        self._on_annotation = handler

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def scan_for_annotations(self, file_path: str | Path) -> list[Annotation]:
        """Return all LIDCO annotations found in *file_path*."""
        p = Path(file_path)
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

        annotations: list[Annotation] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # Multi-line block: `# LIDCO: |`
            if _BLOCK_START_RE.match(line):
                block_lines: list[str] = []
                j = i + 1
                while j < len(lines):
                    cm = _COMMENT_LINE_RE.match(lines[j])
                    if cm:
                        block_lines.append(cm.group(1).strip())
                        j += 1
                    else:
                        break
                if block_lines:
                    instruction = " ".join(block_lines)
                    ctx_start = max(0, i - 3)
                    ctx_end = min(len(lines), j + 3)
                    annotations.append(Annotation(
                        file_path=str(p),
                        line_number=i + 1,
                        instruction=instruction,
                        context_lines=lines[ctx_start:ctx_end],
                    ))
                i = j
                continue

            # Single-line: `# LIDCO: do X`
            m = _ANNOTATION_RE.match(line)
            if m:
                instruction = m.group(1).strip()
                ctx_start = max(0, i - 3)
                ctx_end = min(len(lines), i + 4)
                annotations.append(Annotation(
                    file_path=str(p),
                    line_number=i + 1,
                    instruction=instruction,
                    context_lines=lines[ctx_start:ctx_end],
                ))
            i += 1

        return annotations

    def remove_annotations(self, file_path: str | Path) -> int:
        """Remove all LIDCO annotation lines from file. Returns count removed."""
        p = Path(file_path)
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError:
            return 0

        new_lines: list[str] = []
        removed = 0
        i = 0
        while i < len(lines):
            line = lines[i].rstrip("\n\r")
            if _BLOCK_START_RE.match(line):
                # Skip block start + continuation comment lines
                j = i + 1
                while j < len(lines) and _COMMENT_LINE_RE.match(lines[j].rstrip("\n\r")):
                    j += 1
                removed += j - i
                i = j
                continue
            if _ANNOTATION_RE.match(line):
                removed += 1
                i += 1
                continue
            new_lines.append(lines[i])
            i += 1

        if removed > 0:
            p.write_text("".join(new_lines), encoding="utf-8")
        return removed

    # ------------------------------------------------------------------
    # Directory scanning
    # ------------------------------------------------------------------

    def _iter_source_files(self) -> list[Path]:
        """Yield all non-skipped source files under watch path."""
        result: list[Path] = []
        for p in self._watch_path.rglob("*"):
            if p.is_dir():
                continue
            # Skip hidden dirs and known non-source dirs
            if any(part.startswith(".") or part in _SKIP_DIRS for part in p.parts):
                continue
            # Only scan text-like source files
            if p.suffix in {
                ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
                ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php",
                ".sh", ".bash", ".yaml", ".yml", ".toml", ".json",
            }:
                result.append(p)
        return result

    def scan_all(self) -> list[Annotation]:
        """Scan all files in watch path for annotations. Used by --once mode."""
        all_annotations: list[Annotation] = []
        for p in self._iter_source_files():
            all_annotations.extend(self.scan_for_annotations(p))
        return all_annotations

    def _get_changed_files(self) -> list[Path]:
        """Return files whose mtime changed since last check."""
        changed: list[Path] = []
        for p in self._iter_source_files():
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            key = str(p)
            if key not in self._mtimes or self._mtimes[key] != mtime:
                self._mtimes[key] = mtime
                changed.append(p)
        return changed

    # ------------------------------------------------------------------
    # Watch loop
    # ------------------------------------------------------------------

    def watch_once(self) -> list[Annotation]:
        """Single scan pass — used for testing and --once CLI mode."""
        found: list[Annotation] = []
        for p in self._get_changed_files():
            annotations = self.scan_for_annotations(p)
            for ann in annotations:
                found.append(ann)
                if self._on_annotation:
                    try:
                        self._on_annotation(ann)
                    except Exception:
                        logger.exception("Error in annotation handler for %s", p)
        return found

    def start(self, poll_interval_s: float = 1.0) -> None:
        """Block and poll for annotation changes. Ctrl+C to stop."""
        self._running = True
        logger.info("Watching %s for LIDCO annotations...", self._watch_path)
        try:
            while self._running:
                self.watch_once()
                time.sleep(poll_interval_s)
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False
