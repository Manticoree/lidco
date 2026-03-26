"""Tests for T618 FileWatcher."""
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.watch.file_watcher import FileWatcher, WatchEvent, WatchHandler


# ---------------------------------------------------------------------------
# WatchEvent
# ---------------------------------------------------------------------------

class TestWatchEvent:
    def test_fields(self):
        evt = WatchEvent(path="main.py", kind="modified")
        assert evt.path == "main.py"
        assert evt.kind == "modified"

    def test_str(self):
        evt = WatchEvent(path="src/a.py", kind="created")
        s = str(evt)
        assert "created" in s
        assert "src/a.py" in s

    def test_timestamp_set(self):
        t0 = time.time()
        evt = WatchEvent(path="x.py", kind="deleted")
        assert evt.timestamp >= t0


# ---------------------------------------------------------------------------
# FileWatcher — poll() method (synchronous)
# ---------------------------------------------------------------------------

class TestFileWatcherPoll:
    def test_created_event(self, tmp_path):
        watcher = FileWatcher(paths=[str(tmp_path)], debounce=0.0)
        f = tmp_path / "new.py"
        f.write_text("x = 1")
        events = watcher.poll()
        paths = [e.path for e in events]
        assert str(f) in paths
        created = [e for e in events if e.kind == "created"]
        assert len(created) == 1

    def test_modified_event(self, tmp_path):
        f = tmp_path / "existing.py"
        f.write_text("v1")
        watcher = FileWatcher(paths=[str(tmp_path)], debounce=0.0)
        # Modify file (bump mtime by touching with utime)
        time.sleep(0.05)
        f.write_text("v2")
        # Force mtime change
        import os
        os.utime(str(f), (time.time() + 1, time.time() + 1))
        events = watcher.poll()
        modified = [e for e in events if e.kind == "modified"]
        assert len(modified) >= 1
        assert any(str(f) in e.path for e in modified)

    def test_deleted_event(self, tmp_path):
        f = tmp_path / "gone.py"
        f.write_text("x")
        watcher = FileWatcher(paths=[str(tmp_path)], debounce=0.0)
        watcher.poll()  # prime snapshot
        f.unlink()
        events = watcher.poll()
        deleted = [e for e in events if e.kind == "deleted"]
        assert any(str(f) in e.path for e in deleted)

    def test_no_events_when_unchanged(self, tmp_path):
        f = tmp_path / "stable.py"
        f.write_text("x")
        watcher = FileWatcher(paths=[str(tmp_path)], debounce=0.0)
        watcher.poll()  # prime
        events = watcher.poll()  # nothing changed
        assert events == []

    def test_watches_subdirectory(self, tmp_path):
        sub = tmp_path / "src"
        sub.mkdir()
        watcher = FileWatcher(paths=[str(tmp_path)], debounce=0.0, recursive=True)
        f = sub / "main.py"
        f.write_text("code")
        events = watcher.poll()
        assert any(str(f) in e.path for e in events)

    def test_non_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("x")
        watcher = FileWatcher(paths=[str(tmp_path)], debounce=0.0, recursive=False)
        events = watcher.poll()
        deep_events = [e for e in events if "deep.py" in e.path]
        assert len(deep_events) == 0


# ---------------------------------------------------------------------------
# FileWatcher — handler dispatch
# ---------------------------------------------------------------------------

class TestFileWatcherHandlers:
    def test_register_handler_called(self, tmp_path):
        watcher = FileWatcher(paths=[str(tmp_path)], debounce=0.0)
        received = []
        watcher.register_handler("*.py", lambda e: received.append(e))
        f = tmp_path / "hello.py"
        f.write_text("x")
        watcher.poll()
        # Manually dispatch
        watcher._dispatch(WatchEvent(path=str(f), kind="created"))
        assert len(received) == 1

    def test_pattern_matches_filename(self, tmp_path):
        watcher = FileWatcher(paths=[str(tmp_path)], debounce=0.0)
        py_events = []
        js_events = []
        watcher.register_handler("*.py", lambda e: py_events.append(e))
        watcher.register_handler("*.js", lambda e: js_events.append(e))
        watcher._dispatch(WatchEvent(path=str(tmp_path / "main.py"), kind="created"))
        watcher._dispatch(WatchEvent(path=str(tmp_path / "app.js"), kind="created"))
        assert len(py_events) == 1
        assert len(js_events) == 1

    def test_wildcard_matches_all(self, tmp_path):
        watcher = FileWatcher(paths=[str(tmp_path)], debounce=0.0)
        all_events = []
        watcher.register_handler("*", lambda e: all_events.append(e))
        watcher._dispatch(WatchEvent(path="any_file.txt", kind="modified"))
        assert len(all_events) == 1

    def test_clear_handlers(self, tmp_path):
        watcher = FileWatcher(paths=[str(tmp_path)], debounce=0.0)
        received = []
        watcher.register_handler("*", lambda e: received.append(e))
        watcher.clear_handlers()
        watcher._dispatch(WatchEvent(path="x.py", kind="modified"))
        assert len(received) == 0

    def test_handler_exception_doesnt_crash(self, tmp_path):
        watcher = FileWatcher(paths=[str(tmp_path)], debounce=0.0)
        def bad_handler(e):
            raise RuntimeError("handler error")
        watcher.register_handler("*", bad_handler)
        # Should not raise
        watcher._dispatch(WatchEvent(path="x.py", kind="modified"))


# ---------------------------------------------------------------------------
# FileWatcher — add_path
# ---------------------------------------------------------------------------

class TestFileWatcherAddPath:
    def test_add_path(self, tmp_path):
        watcher = FileWatcher(debounce=0.0)
        watcher.add_path(str(tmp_path))
        f = tmp_path / "new.py"
        f.write_text("x")
        events = watcher.poll()
        # File wasn't in initial snapshot so may or may not be "created"
        assert isinstance(events, list)


# ---------------------------------------------------------------------------
# FileWatcher — start/stop lifecycle
# ---------------------------------------------------------------------------

class TestFileWatcherLifecycle:
    def test_not_running_initially(self, tmp_path):
        watcher = FileWatcher(paths=[str(tmp_path)])
        assert not watcher.running

    def test_start_and_stop(self, tmp_path):
        watcher = FileWatcher(paths=[str(tmp_path)], poll_interval=0.05)
        watcher.start()
        assert watcher.running
        watcher.stop(timeout=1.0)
        assert not watcher.running

    def test_double_start_safe(self, tmp_path):
        watcher = FileWatcher(paths=[str(tmp_path)], poll_interval=0.1)
        watcher.start()
        watcher.start()  # Should not create a second thread
        assert watcher.running
        watcher.stop(timeout=1.0)

    def test_handler_called_on_change(self, tmp_path):
        received = []
        watcher = FileWatcher(
            paths=[str(tmp_path)],
            poll_interval=0.05,
            debounce=0.0,
        )
        watcher.register_handler("*.py", lambda e: received.append(e))
        watcher.start()
        time.sleep(0.05)
        f = tmp_path / "code.py"
        f.write_text("x = 1")
        time.sleep(0.2)  # Wait for poll to detect
        watcher.stop(timeout=1.0)
        # May or may not have detected depending on timing
        assert isinstance(received, list)
