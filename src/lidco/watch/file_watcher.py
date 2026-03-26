"""
File Watcher — monitor filesystem changes via polling (no inotify/kqueue deps).

Uses os.stat() mtime polling in a background thread. Suitable for development
workflows where near-real-time detection (1–2s latency) is sufficient.

Features:
- Watch files and directories by glob patterns
- Events: created, modified, deleted
- Multiple handlers per pattern
- Debounce to suppress rapid repeated events
- Thread-safe start/stop

Stdlib only (threading, os, time, fnmatch, pathlib).
"""

from __future__ import annotations

import fnmatch
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WatchEvent:
    """A single filesystem change event."""
    path: str
    kind: str           # "created" | "modified" | "deleted"
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        return f"[{self.kind}] {self.path}"


@dataclass
class WatchHandler:
    """A registered handler for a file pattern."""
    pattern: str
    callback: Callable[[WatchEvent], None]
    recursive: bool = True


# ---------------------------------------------------------------------------
# FileWatcher
# ---------------------------------------------------------------------------

class FileWatcher:
    """
    Poll-based file watcher.

    Parameters
    ----------
    paths : list[str]
        Directories or files to watch.
    poll_interval : float
        Seconds between polls (default 1.0).
    debounce : float
        Minimum seconds between duplicate events for the same path (default 0.5).
    recursive : bool
        Whether to watch subdirectories recursively.
    """

    def __init__(
        self,
        paths: list[str] | None = None,
        poll_interval: float = 1.0,
        debounce: float = 0.5,
        recursive: bool = True,
    ) -> None:
        self._watch_paths: list[Path] = [Path(p) for p in (paths or [])]
        self._poll_interval = poll_interval
        self._debounce = debounce
        self._recursive = recursive

        self._handlers: list[WatchHandler] = []
        self._mtimes: dict[str, float] = {}   # path → last mtime
        self._last_event: dict[str, float] = {}  # path → last event time

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Prime the snapshot
        self._snapshot()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def add_path(self, path: str) -> None:
        """Add a directory or file to watch."""
        with self._lock:
            self._watch_paths.append(Path(path))
            self._snapshot()

    def register_handler(
        self,
        pattern: str,
        callback: Callable[[WatchEvent], None],
        recursive: bool = True,
    ) -> None:
        """
        Register a handler for file events matching a glob pattern.

        Parameters
        ----------
        pattern : str
            Glob pattern, e.g. "*.py", "src/**/*.ts", or "*" for all.
        callback : Callable[[WatchEvent], None]
            Called with a WatchEvent when a matching file changes.
        recursive : bool
            Whether pattern applies recursively.
        """
        with self._lock:
            self._handlers.append(WatchHandler(pattern=pattern, callback=callback, recursive=recursive))

    def clear_handlers(self) -> None:
        """Remove all registered handlers."""
        with self._lock:
            self._handlers.clear()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start watching in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="FileWatcher")
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        """Stop the background watcher thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ------------------------------------------------------------------
    # Manual poll (for testing / synchronous use)
    # ------------------------------------------------------------------

    def poll(self) -> list[WatchEvent]:
        """
        Perform one poll cycle and return any detected events.
        Does NOT call registered handlers — use for testing or sync use.
        """
        return self._detect_changes()

    # ------------------------------------------------------------------
    # Private — polling
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            events = self._detect_changes()
            for evt in events:
                self._dispatch(evt)
            self._stop_event.wait(timeout=self._poll_interval)

    def _detect_changes(self) -> list[WatchEvent]:
        events: list[WatchEvent] = []
        current: dict[str, float] = {}

        with self._lock:
            watch_paths = list(self._watch_paths)

        for root in watch_paths:
            if not root.exists():
                continue
            if root.is_file():
                self._stat_file(root, current, events)
            elif root.is_dir():
                if self._recursive:
                    for dirpath, _, filenames in os.walk(str(root)):
                        for fname in filenames:
                            self._stat_file(Path(dirpath) / fname, current, events)
                else:
                    for child in root.iterdir():
                        if child.is_file():
                            self._stat_file(child, current, events)

        # Detect deletions
        with self._lock:
            old_paths = set(self._mtimes.keys())
        for p in old_paths - set(current.keys()):
            if self._debounce_ok(p):
                events.append(WatchEvent(path=p, kind="deleted"))

        with self._lock:
            self._mtimes = current
        return events

    def _stat_file(
        self, path: Path, current: dict[str, float], events: list[WatchEvent]
    ) -> None:
        key = str(path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        current[key] = mtime

        with self._lock:
            old_mtime = self._mtimes.get(key)

        if old_mtime is None:
            if self._debounce_ok(key):
                events.append(WatchEvent(path=key, kind="created"))
        elif mtime > old_mtime and self._debounce_ok(key):
            events.append(WatchEvent(path=key, kind="modified"))

    def _debounce_ok(self, path: str) -> bool:
        now = time.time()
        with self._lock:
            last = self._last_event.get(path, 0.0)
            if now - last < self._debounce:
                return False
            self._last_event[path] = now
        return True

    def _dispatch(self, evt: WatchEvent) -> None:
        with self._lock:
            handlers = list(self._handlers)

        for handler in handlers:
            fname = os.path.basename(evt.path)
            full = evt.path
            if fnmatch.fnmatch(fname, handler.pattern) or fnmatch.fnmatch(full, handler.pattern):
                try:
                    handler.callback(evt)
                except Exception:
                    pass

    def _snapshot(self) -> None:
        """Build initial mtime snapshot (called during init or add_path)."""
        for root in self._watch_paths:
            if not root.exists():
                continue
            if root.is_file():
                try:
                    self._mtimes[str(root)] = root.stat().st_mtime
                except OSError:
                    pass
            elif root.is_dir():
                if self._recursive:
                    for dirpath, _, filenames in os.walk(str(root)):
                        for fname in filenames:
                            p = Path(dirpath) / fname
                            try:
                                self._mtimes[str(p)] = p.stat().st_mtime
                            except OSError:
                                pass
                else:
                    for child in root.iterdir():
                        if child.is_file():
                            try:
                                self._mtimes[str(child)] = child.stat().st_mtime
                            except OSError:
                                pass
