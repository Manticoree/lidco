"""AICommentScanner — detect and process # AI! / # AI? inline instructions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Regex patterns for AI comments
_EXECUTE_RE = re.compile(r"^\s*(?:#|//)\s*AI!\s*(.*)$")
_ASK_RE = re.compile(r"^\s*(?:#|//)\s*AI\?\s*(.*)$")

# Directories to skip when scanning
_SKIP_DIRS = frozenset({".git", "__pycache__", "node_modules", ".venv", "venv"})

# Extensions to scan
_SOURCE_EXTS = frozenset({".py", ".js", ".ts"})


@dataclass
class AIComment:
    file_path: str
    line_number: int  # 1-based
    instruction: str
    mode: str  # "execute" or "ask"
    context_lines: list[str] = field(default_factory=list)


class AICommentScanner:
    """Scan source files for # AI! and # AI? inline instructions."""

    def __init__(self, watch_path: Path | None = None) -> None:
        self._watch_path = Path(watch_path) if watch_path else Path.cwd()

    # ------------------------------------------------------------------
    # File scanning
    # ------------------------------------------------------------------

    def scan_file(self, file_path: str | Path) -> list[AIComment]:
        """Read file and return all AI! / AI? comments found."""
        p = Path(file_path)
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

        results: list[AIComment] = []
        for i, line in enumerate(lines):
            m_exec = _EXECUTE_RE.match(line)
            m_ask = _ASK_RE.match(line)

            if m_exec:
                ctx_start = max(0, i - 3)
                ctx_lines = lines[ctx_start:i]
                results.append(AIComment(
                    file_path=str(p),
                    line_number=i + 1,
                    instruction=m_exec.group(1).strip(),
                    mode="execute",
                    context_lines=ctx_lines,
                ))
            elif m_ask:
                ctx_start = max(0, i - 3)
                ctx_lines = lines[ctx_start:i]
                results.append(AIComment(
                    file_path=str(p),
                    line_number=i + 1,
                    instruction=m_ask.group(1).strip(),
                    mode="ask",
                    context_lines=ctx_lines,
                ))

        return results

    # ------------------------------------------------------------------
    # Directory scanning
    # ------------------------------------------------------------------

    def scan_directory(self, path: Path | None = None) -> list[AIComment]:
        """Recursively scan for AI comments in .py, .js, .ts files."""
        scan_root = Path(path) if path else self._watch_path
        results: list[AIComment] = []

        for p in scan_root.rglob("*"):
            if p.is_dir():
                continue
            # Skip unwanted dirs
            if any(part in _SKIP_DIRS or part.startswith(".") for part in p.parts):
                continue
            if p.suffix not in _SOURCE_EXTS:
                continue
            results.extend(self.scan_file(p))

        return results

    # ------------------------------------------------------------------
    # Comment removal
    # ------------------------------------------------------------------

    def remove_comments(self, file_path: str | Path) -> int:
        """Remove AI! and AI? comment lines from file. Returns count removed."""
        p = Path(file_path)
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError:
            return 0

        new_lines: list[str] = []
        removed = 0
        for line in lines:
            stripped = line.rstrip("\n\r")
            if _EXECUTE_RE.match(stripped) or _ASK_RE.match(stripped):
                removed += 1
            else:
                new_lines.append(line)

        if removed > 0:
            p.write_text("".join(new_lines), encoding="utf-8")

        return removed

    # ------------------------------------------------------------------
    # Watcher integration
    # ------------------------------------------------------------------

    def integrate_with_watcher(self, watcher: object) -> None:
        """Register scan_file callback on a watcher object."""

        def _callback(event: object) -> None:
            # Try to get a file path from the event
            file_path: str | None = None
            for attr in ("file_path", "src_path", "path", "file"):
                val = getattr(event, attr, None)
                if val:
                    file_path = str(val)
                    break
            if file_path:
                self.scan_file(file_path)

        # Try common watcher callback registration methods
        for method_name in ("on_change", "add_handler", "register_callback", "set_annotation_handler"):
            method = getattr(watcher, method_name, None)
            if callable(method):
                method(_callback)
                return

        # Fallback: store directly
        if hasattr(watcher, "_on_annotation"):
            watcher._on_annotation = _callback  # type: ignore[attr-defined]
