"""Tests for Q41 — CheckpointManager (Task 283)."""
from __future__ import annotations

import pytest
from pathlib import Path

from lidco.cli.checkpoint import Checkpoint, CheckpointManager


class TestCheckpointRecord:
    def test_record_existing_file(self, tmp_path):
        p = tmp_path / "a.py"
        p.write_text("old content")
        mgr = CheckpointManager()
        mgr.record(str(p), "old content")
        assert mgr.count() == 1

    def test_record_new_file(self):
        mgr = CheckpointManager()
        mgr.record("/tmp/new.py", None)
        assert mgr.count() == 1
        cp = mgr.peek(1)[0]
        assert cp.content is None
        assert cp.existed is False

    def test_record_existing_sets_existed_true(self):
        mgr = CheckpointManager()
        mgr.record("/tmp/x.py", "content")
        cp = mgr.peek(1)[0]
        assert cp.existed is True

    def test_record_respects_max_limit(self):
        from lidco.cli.checkpoint import _MAX_CHECKPOINTS
        mgr = CheckpointManager()
        for i in range(_MAX_CHECKPOINTS + 10):
            mgr.record(f"/tmp/f{i}.py", "x")
        assert mgr.count() == _MAX_CHECKPOINTS


class TestCheckpointRestore:
    def test_restore_overwrites_file(self, tmp_path):
        p = tmp_path / "f.py"
        p.write_text("new content")
        mgr = CheckpointManager()
        mgr.record(str(p), "old content")
        restored = mgr.restore(1)
        assert str(p) in restored
        assert p.read_text() == "old content"

    def test_restore_deletes_new_file(self, tmp_path):
        p = tmp_path / "new.py"
        p.write_text("created content")
        mgr = CheckpointManager()
        mgr.record(str(p), None)  # file did not exist
        restored = mgr.restore(1)
        assert str(p) in restored
        assert not p.exists()

    def test_restore_multiple(self, tmp_path):
        p1 = tmp_path / "a.py"
        p2 = tmp_path / "b.py"
        p1.write_text("a-new")
        p2.write_text("b-new")
        mgr = CheckpointManager()
        mgr.record(str(p1), "a-old")
        mgr.record(str(p2), "b-old")
        restored = mgr.restore(2)
        assert len(restored) == 2
        assert p1.read_text() == "a-old"
        assert p2.read_text() == "b-old"

    def test_restore_empty_stack_returns_empty(self):
        mgr = CheckpointManager()
        assert mgr.restore(1) == []

    def test_restore_reduces_count(self, tmp_path):
        p = tmp_path / "x.py"
        p.write_text("new")
        mgr = CheckpointManager()
        mgr.record(str(p), "old")
        mgr.restore(1)
        assert mgr.count() == 0

    def test_restore_clamps_to_stack_size(self, tmp_path):
        p = tmp_path / "f.py"
        p.write_text("new")
        mgr = CheckpointManager()
        mgr.record(str(p), "old")
        # Requesting more than available should not raise
        restored = mgr.restore(99)
        assert len(restored) <= 1


class TestCheckpointPeek:
    def test_peek_returns_most_recent_first(self):
        mgr = CheckpointManager()
        mgr.record("/a.py", "a")
        mgr.record("/b.py", "b")
        mgr.record("/c.py", "c")
        recent = mgr.peek(2)
        assert recent[0].path == "/c.py"
        assert recent[1].path == "/b.py"

    def test_peek_does_not_modify_stack(self):
        mgr = CheckpointManager()
        mgr.record("/x.py", "x")
        mgr.peek(5)
        assert mgr.count() == 1


class TestCheckpointClear:
    def test_clear_empties_stack(self):
        mgr = CheckpointManager()
        mgr.record("/a.py", "a")
        mgr.record("/b.py", "b")
        mgr.clear()
        assert mgr.count() == 0
