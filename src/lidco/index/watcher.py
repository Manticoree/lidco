"""Watchdog-based file system watcher for automatic index updates.

When ``config.index.auto_watch = true``, a background thread monitors the
project directory and triggers incremental re-indexing whenever source files
are created, modified, or deleted.

Changes are debounced (default 500 ms) so that a burst of writes (e.g. a
``git checkout``) results in a single incremental pass, not dozens.

Usage::

    watcher = IndexWatcher(project_dir, db_path, status_callback=fn)
    watcher.start()
    ...
    watcher.stop()
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# File extensions that should trigger a re-index
_WATCH_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".rs", ".cpp", ".c", ".rb",
    ".md", ".yaml", ".yml", ".toml", ".json",
})

# Directories to ignore entirely
_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", "venv", ".venv",
    "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
    ".lidco",
})

_DEBOUNCE_SECONDS = 0.5


class IndexWatcher:
    """Monitors a project directory and triggers incremental re-indexing.

    Args:
        project_dir: Root directory to watch.
        db_path: Path to the ``project_index.db`` SQLite file.
        debounce: Seconds to wait after the last change before re-indexing.
        status_callback: Optional ``(message: str) -> None`` to surface
            status messages (e.g. to the CLI status bar).
    """

    def __init__(
        self,
        project_dir: Path,
        db_path: Path,
        *,
        debounce: float = _DEBOUNCE_SECONDS,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._project_dir = project_dir
        self._db_path = db_path
        self._debounce = debounce
        self._status_callback = status_callback

        self._observer: object | None = None
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._running = False

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Start the background watcher thread.

        Returns ``True`` if the watcher started successfully, ``False`` if
        the ``watchdog`` library is not installed.
        """
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            logger.info(
                "watchdog not installed — auto-indexing disabled. "
                "Install with: pip install watchdog"
            )
            return False

        if not self._db_path.exists():
            logger.debug(
                "Index DB not found at %s — auto-watch skipped (run /index first)",
                self._db_path,
            )
            return False

        event_handler = _Handler(self._on_change)
        observer = Observer()
        observer.schedule(event_handler, str(self._project_dir), recursive=True)  # type: ignore[arg-type]
        observer.start()
        self._observer = observer
        self._running = True
        logger.info("Index watcher started for %s", self._project_dir)
        return True

    def stop(self) -> None:
        """Stop the background watcher thread."""
        self._running = False
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        if self._observer is not None:
            try:
                self._observer.stop()  # type: ignore[attr-defined]
                self._observer.join(timeout=2)  # type: ignore[attr-defined]
            except Exception as exc:
                logger.debug("Error stopping observer: %s", exc)
            self._observer = None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_change(self, path: str) -> None:
        """Called by the event handler when a relevant file changes."""
        if not self._running:
            return
        # Debounce: reset the timer on every new event
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._reindex)
            self._timer.daemon = True
            self._timer.start()

    def _reindex(self) -> None:
        """Run an incremental index pass in the background thread."""
        if not self._running:
            return
        try:
            from lidco.index.db import IndexDatabase
            from lidco.index.project_indexer import ProjectIndexer

            db = IndexDatabase(self._db_path)
            try:
                indexer = ProjectIndexer(project_dir=self._project_dir, db=db)
                result = indexer.run_incremental_index()
                changed = result.added + result.updated + result.deleted
                if changed:
                    msg = f"Index updated ({changed} file{'s' if changed != 1 else ''})"
                    logger.debug(msg)
                    if self._status_callback is not None:
                        try:
                            self._status_callback(msg)
                        except Exception:
                            pass
            finally:
                db.close()
        except Exception as exc:
            logger.debug("Auto-index error: %s", exc)


class _Handler:
    """watchdog FileSystemEventHandler that filters by extension / directory."""

    def __init__(self, callback: Callable[[str], None]) -> None:
        self._callback = callback

    # watchdog calls these dispatch methods on the handler
    def dispatch(self, event: object) -> None:  # type: ignore[override]
        from watchdog.events import DirModifiedEvent
        if isinstance(event, DirModifiedEvent):
            return
        src = getattr(event, "src_path", "")
        self._maybe_trigger(src)
        dest = getattr(event, "dest_path", "")
        if dest:
            self._maybe_trigger(dest)

    def _maybe_trigger(self, path: str) -> None:
        if not path:
            return
        p = Path(path)
        # Skip ignored directories
        if any(part in _SKIP_DIRS for part in p.parts):
            return
        if p.suffix.lower() not in _WATCH_EXTENSIONS:
            return
        self._callback(path)
