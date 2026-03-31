"""Q148: Temporary file cleaner."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class CleanupTarget:
    path: str
    size_bytes: int
    age_seconds: float
    reason: str


@dataclass
class CleanupResult:
    removed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    bytes_freed: int = 0
    errors: list[str] = field(default_factory=list)


_DEFAULT_PATTERNS = ["*.pyc", "__pycache__", ".tmp", "*.bak", "*.swp"]


class TempCleaner:
    """Scan and remove temporary / generated files."""

    def __init__(
        self,
        patterns: Optional[List[str]] = None,
        *,
        _listdir: Optional[Callable[..., list[str]]] = None,
        _isfile: Optional[Callable[..., bool]] = None,
        _isdir: Optional[Callable[..., bool]] = None,
        _getsize: Optional[Callable[..., int]] = None,
        _getmtime: Optional[Callable[..., float]] = None,
        _remove: Optional[Callable[..., None]] = None,
        _rmdir: Optional[Callable[..., None]] = None,
    ) -> None:
        self._patterns: list[str] = list(patterns) if patterns is not None else list(_DEFAULT_PATTERNS)
        self._listdir = _listdir or os.listdir
        self._isfile = _isfile or os.path.isfile
        self._isdir = _isdir or os.path.isdir
        self._getsize = _getsize or os.path.getsize
        self._getmtime = _getmtime or os.path.getmtime
        self._remove = _remove or os.remove
        self._rmdir = _rmdir or os.rmdir

    # -- pattern management --------------------------------------------------

    def add_pattern(self, pattern: str) -> None:
        if pattern not in self._patterns:
            self._patterns.append(pattern)

    def remove_pattern(self, pattern: str) -> None:
        if pattern in self._patterns:
            self._patterns.remove(pattern)

    @property
    def patterns(self) -> list[str]:
        return list(self._patterns)

    # -- matching ------------------------------------------------------------

    def _matches(self, name: str) -> str:
        """Return the matching pattern or empty string."""
        for pat in self._patterns:
            if pat.startswith("*."):
                ext = pat[1:]  # e.g. ".pyc"
                if name.endswith(ext):
                    return pat
            else:
                if name == pat:
                    return pat
        return ""

    # -- scanning ------------------------------------------------------------

    def _walk(self, root: str):
        """Recursively yield (dirpath, entry_name) pairs."""
        try:
            entries = self._listdir(root)
        except OSError:
            return
        for entry in entries:
            full = os.path.join(root, entry)
            yield root, entry, full
            if self._isdir(full):
                yield from self._walk(full)

    def scan(self, root: str) -> list[CleanupTarget]:
        """Find cleanup targets under *root*."""
        now = time.time()
        targets: list[CleanupTarget] = []
        for dirpath, name, full in self._walk(root):
            pat = self._matches(name)
            if not pat:
                continue
            try:
                size = self._getsize(full) if self._isfile(full) else 0
            except OSError:
                size = 0
            try:
                mtime = self._getmtime(full)
            except OSError:
                mtime = now
            age = now - mtime
            targets.append(CleanupTarget(path=full, size_bytes=size, age_seconds=age, reason=f"matches {pat}"))
        return targets

    # -- cleaning ------------------------------------------------------------

    def clean(self, root: str, dry_run: bool = False) -> CleanupResult:
        """Remove cleanup targets. If *dry_run* is ``True``, skip actual removal."""
        targets = self.scan(root)
        result = CleanupResult()
        for t in targets:
            if dry_run:
                result.skipped.append(t.path)
                continue
            try:
                if self._isdir(t.path):
                    self._rmdir(t.path)
                else:
                    self._remove(t.path)
                result.removed.append(t.path)
                result.bytes_freed += t.size_bytes
            except OSError as exc:
                result.errors.append(f"{t.path}: {exc}")
                result.skipped.append(t.path)
        return result

    # -- estimate ------------------------------------------------------------

    def estimate(self, root: str) -> dict:
        """Return total_files and total_bytes without removing anything."""
        targets = self.scan(root)
        return {
            "total_files": len(targets),
            "total_bytes": sum(t.size_bytes for t in targets),
        }
