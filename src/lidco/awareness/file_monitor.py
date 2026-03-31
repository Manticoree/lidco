"""Watch project files for external changes via mtime polling."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import time
import fnmatch
import threading


@dataclass
class FileChange:
    file_path: str
    change_type: str  # "modified", "created", "deleted"
    old_mtime: float | None
    new_mtime: float | None
    detected_at: float = field(default_factory=time.time)


@dataclass
class MonitorConfig:
    poll_interval: float = 1.0  # seconds
    debounce: float = 0.5  # seconds
    ignore_patterns: list[str] = field(default_factory=lambda: [
        "*.pyc", "__pycache__/*", ".git/*", "*.swp", "*.swo", "*~",
        ".lidco/cache/*", "node_modules/*", ".venv/*",
    ])


class FileMonitor:
    def __init__(self, root_dir: str, config: MonitorConfig | None = None):
        self._root_dir = root_dir
        self._config = config or MonitorConfig()
        self._mtimes: dict[str, float] = {}
        self._callbacks: list = []  # list of callables taking FileChange
        self._running = False
        self._lock = threading.Lock()
        self._changes: list[FileChange] = []

    @property
    def root_dir(self) -> str:
        return self._root_dir

    @property
    def config(self) -> MonitorConfig:
        return self._config

    @property
    def is_running(self) -> bool:
        return self._running

    def on_change(self, callback) -> None:
        """Register a callback for file changes."""
        self._callbacks = [*self._callbacks, callback]

    def scan(self) -> list[FileChange]:
        """Scan for changes since last scan. Returns list of changes."""
        changes: list[FileChange] = []
        current_files: dict[str, float] = {}

        if not os.path.isdir(self._root_dir):
            return changes

        for dirpath, dirnames, filenames in os.walk(self._root_dir):
            # Filter ignored dirs in-place (os.walk requires this)
            dirnames[:] = [d for d in dirnames if not self._is_ignored(os.path.join(dirpath, d))]

            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                if self._is_ignored(fpath):
                    continue
                try:
                    mtime = os.path.getmtime(fpath)
                    current_files[fpath] = mtime
                except OSError:
                    continue

        with self._lock:
            # Detect modifications and creations
            for fpath, mtime in current_files.items():
                old_mtime = self._mtimes.get(fpath)
                if old_mtime is None:
                    if self._mtimes:  # Only report created if we've scanned before
                        changes.append(FileChange(
                            file_path=fpath, change_type="created",
                            old_mtime=None, new_mtime=mtime,
                        ))
                elif mtime != old_mtime:
                    changes.append(FileChange(
                        file_path=fpath, change_type="modified",
                        old_mtime=old_mtime, new_mtime=mtime,
                    ))

            # Detect deletions
            if self._mtimes:
                for fpath in self._mtimes:
                    if fpath not in current_files:
                        changes.append(FileChange(
                            file_path=fpath, change_type="deleted",
                            old_mtime=self._mtimes[fpath], new_mtime=None,
                        ))

            # Update state
            self._mtimes = dict(current_files)
            self._changes = [*self._changes, *changes]

        # Notify callbacks
        for change in changes:
            for cb in self._callbacks:
                try:
                    cb(change)
                except Exception:
                    pass

        return changes

    def _is_ignored(self, path: str) -> bool:
        """Check if path matches any ignore pattern."""
        rel = os.path.relpath(path, self._root_dir)
        for pattern in self._config.ignore_patterns:
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern):
                return True
        return False

    def get_changes(self) -> list[FileChange]:
        """Get all accumulated changes."""
        with self._lock:
            return list(self._changes)

    def clear_changes(self) -> None:
        """Clear accumulated changes."""
        with self._lock:
            self._changes = []

    def start(self) -> None:
        """Start monitoring (sets flag, actual polling would be in a thread)."""
        self._running = True

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False

    def snapshot(self) -> dict[str, float]:
        """Get current mtime snapshot."""
        with self._lock:
            return dict(self._mtimes)
