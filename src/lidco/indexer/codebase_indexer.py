"""DeepWiki-style codebase indexer — builds a semantic index with file summaries."""
from __future__ import annotations

import ast
import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileEntry:
    path: str
    summary: str          # top-level classes/functions as a summary line
    imports: list[str]    # modules this file imports
    exports: list[str]    # public names defined here
    hash: str             # sha256 of content for change detection
    lines: int


@dataclass
class IndexReport:
    total_files: int
    indexed_files: int
    skipped_files: int
    index: dict[str, FileEntry]   # path → FileEntry
    architecture_summary: str     # multi-line ASCII summary

    def format_summary(self) -> str:
        return (
            f"Codebase Index: {self.indexed_files}/{self.total_files} files\n"
            + self.architecture_summary
        )


_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "dist", "build"}


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]


def _extract_entry(path: Path, content: str) -> FileEntry:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return FileEntry(path=str(path), summary="(unparseable)", imports=[], exports=[], hash=_sha256(content), lines=content.count("\n"))

    imports: list[str] = []
    exports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import,)):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                exports.append(f"def {node.name}")
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                exports.append(f"class {node.name}")

    summary = ", ".join(exports[:8]) or "(no public API)"
    return FileEntry(
        path=str(path),
        summary=summary,
        imports=list(dict.fromkeys(imports))[:10],
        exports=exports[:20],
        hash=_sha256(content),
        lines=content.count("\n"),
    )


class CodebaseIndexer:
    """Builds and maintains a live index of a Python codebase.

    Usage:
        indexer = CodebaseIndexer("/path/to/project")
        report = indexer.build()
        indexer.start_background(interval=120)  # auto-refresh every 2 min
        indexer.stop_background()
    """

    def __init__(self, root: str | Path = ".", cache_path: str | None = None) -> None:
        self.root = Path(root).resolve()
        self._cache_path = Path(cache_path) if cache_path else self.root / ".lidco" / "codebase_index.json"
        self._index: dict[str, FileEntry] = {}
        self._lock = threading.Lock()
        self._bg_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def _iter_py_files(self) -> list[Path]:
        result: list[Path] = []
        for p in self.root.rglob("*.py"):
            if not any(part in _SKIP_DIRS for part in p.parts):
                result.append(p)
        return result

    def _build_architecture_summary(self, index: dict[str, FileEntry]) -> str:
        lines: list[str] = []
        # Group by top-level package
        packages: dict[str, list[FileEntry]] = {}
        for entry in index.values():
            rel = Path(entry.path).relative_to(self.root) if Path(entry.path).is_absolute() else Path(entry.path)
            pkg = rel.parts[0] if len(rel.parts) > 1 else "(root)"
            packages.setdefault(pkg, []).append(entry)
        for pkg, entries in sorted(packages.items()):
            lines.append(f"[{pkg}] — {len(entries)} files")
            for e in sorted(entries, key=lambda x: -len(x.exports))[:3]:
                p = Path(e.path)
                name = p.stem
                lines.append(f"  {name}: {e.summary[:60]}")
        return "\n".join(lines)

    def build(self) -> IndexReport:
        """Scan the project and build (or refresh) the index."""
        files = self._iter_py_files()
        new_index: dict[str, FileEntry] = {}
        indexed = 0
        skipped = 0

        for path in files:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                entry = _extract_entry(path, content)
                new_index[str(path)] = entry
                indexed += 1
            except OSError:
                skipped += 1

        with self._lock:
            self._index = new_index

        arch = self._build_architecture_summary(new_index)
        return IndexReport(
            total_files=len(files),
            indexed_files=indexed,
            skipped_files=skipped,
            index=new_index,
            architecture_summary=arch,
        )

    def get_index(self) -> dict[str, FileEntry]:
        with self._lock:
            return dict(self._index)

    def lookup(self, name: str) -> list[FileEntry]:
        """Find files that export a given name."""
        results: list[FileEntry] = []
        with self._lock:
            for entry in self._index.values():
                if any(name in exp for exp in entry.exports):
                    results.append(entry)
        return results

    def save(self) -> None:
        """Persist index to cache file."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            data = {k: vars(v) for k, v in self._index.items()}
        self._cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> bool:
        """Load index from cache file. Returns True if successful."""
        if not self._cache_path.exists():
            return False
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            with self._lock:
                self._index = {k: FileEntry(**v) for k, v in data.items()}
            return True
        except Exception:
            return False

    def start_background(self, interval: int = 120) -> None:
        """Start background refresh thread."""
        if self._bg_thread and self._bg_thread.is_alive():
            return
        self._stop_event.clear()

        def _run() -> None:
            while not self._stop_event.wait(interval):
                try:
                    self.build()
                except Exception:
                    pass

        self._bg_thread = threading.Thread(target=_run, daemon=True, name="codebase-indexer")
        self._bg_thread.start()

    def stop_background(self) -> None:
        """Stop background refresh thread."""
        self._stop_event.set()
        if self._bg_thread:
            self._bg_thread.join(timeout=2)
            self._bg_thread = None

    @property
    def is_running(self) -> bool:
        return self._bg_thread is not None and self._bg_thread.is_alive()
