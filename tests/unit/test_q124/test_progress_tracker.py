"""Tests for src/lidco/execution/progress_tracker.py."""
from __future__ import annotations

import time
from unittest.mock import patch

from lidco.execution.progress_tracker import ProgressEntry, ProgressTracker


# ------------------------------------------------------------------ #
# ProgressEntry                                                        #
# ------------------------------------------------------------------ #

class TestProgressEntry:
    def test_fields(self):
        e = ProgressEntry(id="1", name="task1", status="pending")
        assert e.id == "1"
        assert e.name == "task1"
        assert e.status == "pending"
        assert e.started_at is None
        assert e.finished_at is None

    def test_elapsed_no_start(self):
        e = ProgressEntry(id="1", name="t", status="pending")
        assert e.elapsed == 0.0

    def test_elapsed_with_start_and_finish(self):
        e = ProgressEntry(id="1", name="t", status="done", started_at=100.0, finished_at=103.5)
        assert abs(e.elapsed - 3.5) < 0.001

    def test_elapsed_with_start_no_finish(self):
        now = time.monotonic()
        e = ProgressEntry(id="1", name="t", status="running", started_at=now - 1.0)
        assert e.elapsed >= 0.9


# ------------------------------------------------------------------ #
# ProgressTracker                                                      #
# ------------------------------------------------------------------ #

class TestProgressTracker:
    def test_start_creates_running_entry(self):
        tracker = ProgressTracker()
        entry = tracker.start("id1", "task1")
        assert entry.status == "running"
        assert entry.id == "id1"
        assert entry.name == "task1"
        assert entry.started_at is not None

    def test_finish_marks_done(self):
        tracker = ProgressTracker()
        tracker.start("id1", "task1")
        entry = tracker.finish("id1", success=True)
        assert entry.status == "done"
        assert entry.finished_at is not None

    def test_finish_marks_failed(self):
        tracker = ProgressTracker()
        tracker.start("id1", "task1")
        entry = tracker.finish("id1", success=False)
        assert entry.status == "failed"

    def test_get_returns_entry(self):
        tracker = ProgressTracker()
        tracker.start("id1", "task1")
        entry = tracker.get("id1")
        assert entry is not None
        assert entry.name == "task1"

    def test_get_returns_none_for_missing(self):
        tracker = ProgressTracker()
        assert tracker.get("missing") is None

    def test_list_all_returns_all(self):
        tracker = ProgressTracker()
        tracker.start("a", "A")
        tracker.start("b", "B")
        entries = tracker.list_all()
        assert len(entries) == 2

    def test_list_all_empty(self):
        tracker = ProgressTracker()
        assert tracker.list_all() == []

    def test_summary_counts(self):
        tracker = ProgressTracker()
        tracker.start("a", "A")
        tracker.start("b", "B")
        tracker.finish("a", success=True)
        tracker.start("c", "C")
        tracker.finish("c", success=False)
        s = tracker.summary()
        assert s["total"] == 3
        assert s["done"] == 1
        assert s["running"] == 1
        assert s["failed"] == 1
        assert s["pending"] == 0

    def test_summary_empty(self):
        tracker = ProgressTracker()
        s = tracker.summary()
        assert s["total"] == 0

    def test_clear_empties_tracker(self):
        tracker = ProgressTracker()
        tracker.start("a", "A")
        tracker.start("b", "B")
        tracker.clear()
        assert tracker.list_all() == []
        assert tracker.summary()["total"] == 0

    def test_multiple_start_finish_cycle(self):
        tracker = ProgressTracker()
        for i in range(5):
            tracker.start(str(i), f"task{i}")
        for i in range(5):
            tracker.finish(str(i), success=(i % 2 == 0))
        s = tracker.summary()
        assert s["done"] == 3
        assert s["failed"] == 2
        assert s["running"] == 0

    def test_summary_key_names(self):
        tracker = ProgressTracker()
        s = tracker.summary()
        for key in ("total", "done", "running", "failed", "pending"):
            assert key in s
