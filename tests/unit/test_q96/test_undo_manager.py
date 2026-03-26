"""Tests for T615 UndoManager."""
import time
from pathlib import Path

import pytest

from lidco.editing.undo_manager import (
    UndoManager,
    Checkpoint,
    FileSnapshot,
    UndoResult,
)


# ---------------------------------------------------------------------------
# FileSnapshot
# ---------------------------------------------------------------------------

class TestFileSnapshot:
    def test_fields(self):
        snap = FileSnapshot(path="main.py", content="x = 1", existed=True)
        assert snap.path == "main.py"
        assert snap.content == "x = 1"
        assert snap.existed is True

    def test_size(self):
        snap = FileSnapshot(path="a.py", content="hello", existed=True)
        assert snap.size == 5


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

class TestCheckpoint:
    def test_file_count(self):
        cp = Checkpoint(
            label="test",
            snapshots={
                "a.py": FileSnapshot("a.py", "x=1", True),
                "b.py": FileSnapshot("b.py", "y=2", True),
            },
        )
        assert cp.file_count == 2

    def test_summary(self):
        cp = Checkpoint(
            label="before refactor",
            snapshots={"main.py": FileSnapshot("main.py", "pass", True)},
        )
        s = cp.summary()
        assert "before refactor" in s
        assert "1 file" in s


# ---------------------------------------------------------------------------
# UndoManager
# ---------------------------------------------------------------------------

class TestUndoManagerWatch:
    def test_watch_adds_files(self):
        mgr = UndoManager()
        mgr.watch("a.py", "b.py")
        assert "a.py" in mgr.watched_files
        assert "b.py" in mgr.watched_files

    def test_unwatch_removes_files(self):
        mgr = UndoManager()
        mgr.watch("a.py", "b.py")
        mgr.unwatch("a.py")
        assert "a.py" not in mgr.watched_files
        assert "b.py" in mgr.watched_files

    def test_init_with_watched_files(self):
        mgr = UndoManager(watched_files=["x.py", "y.py"])
        assert "x.py" in mgr.watched_files


class TestUndoManagerCheckpoint:
    def test_checkpoint_creates_snapshot(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("x = 1")
        mgr = UndoManager()
        cp = mgr.checkpoint(label="initial", extra_files=[str(f)])
        assert str(f) in cp.snapshots
        assert cp.snapshots[str(f)].content == "x = 1"
        assert cp.snapshots[str(f)].existed is True

    def test_checkpoint_nonexistent_file(self, tmp_path):
        path = str(tmp_path / "missing.py")
        mgr = UndoManager()
        cp = mgr.checkpoint(extra_files=[path])
        assert cp.snapshots[path].existed is False

    def test_checkpoint_label(self, tmp_path):
        mgr = UndoManager()
        cp = mgr.checkpoint(label="my label")
        assert cp.label == "my label"

    def test_checkpoint_clears_redo(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("v1")
        mgr = UndoManager()
        mgr.checkpoint(extra_files=[str(f)])
        f.write_text("v2")
        mgr.checkpoint(extra_files=[str(f)])
        mgr.undo()
        assert mgr.can_redo
        f.write_text("v3")
        mgr.checkpoint(extra_files=[str(f)])  # new checkpoint clears redo
        assert not mgr.can_redo

    def test_max_checkpoints_enforced(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        mgr = UndoManager(max_checkpoints=3)
        for i in range(10):
            f.write_text(f"v{i}")
            mgr.checkpoint(extra_files=[str(f)])
        assert len(mgr._undo_stack) <= 3


class TestUndoManagerUndoRedo:
    def test_undo_restores_file(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("v1")
        mgr = UndoManager()
        mgr.checkpoint(label="v1", extra_files=[str(f)])
        f.write_text("v2")
        mgr.checkpoint(label="v2", extra_files=[str(f)])

        result = mgr.undo()
        assert result.success
        assert f.read_text() == "v1"

    def test_redo_re_applies(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("v1")
        mgr = UndoManager()
        mgr.checkpoint(label="v1", extra_files=[str(f)])
        f.write_text("v2")
        mgr.checkpoint(label="v2", extra_files=[str(f)])
        mgr.undo()
        assert f.read_text() == "v1"
        result = mgr.redo()
        assert result.success
        assert f.read_text() == "v2"

    def test_undo_with_no_history(self):
        mgr = UndoManager()
        result = mgr.undo()
        assert not result.success
        assert result.error != ""

    def test_undo_at_oldest_checkpoint(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        mgr = UndoManager()
        mgr.checkpoint(extra_files=[str(f)])
        result = mgr.undo()
        assert not result.success
        assert "oldest" in result.error.lower() or result.error

    def test_redo_with_nothing(self):
        mgr = UndoManager()
        result = mgr.redo()
        assert not result.success
        assert "nothing to redo" in result.error.lower()

    def test_can_undo_false_initially(self):
        mgr = UndoManager()
        assert not mgr.can_undo

    def test_can_undo_true_after_two_checkpoints(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        mgr = UndoManager()
        mgr.checkpoint(extra_files=[str(f)])
        f.write_text("y")
        mgr.checkpoint(extra_files=[str(f)])
        assert mgr.can_undo

    def test_can_redo_true_after_undo(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        mgr = UndoManager()
        mgr.checkpoint(extra_files=[str(f)])
        f.write_text("y")
        mgr.checkpoint(extra_files=[str(f)])
        mgr.undo()
        assert mgr.can_redo

    def test_undo_deleted_file(self, tmp_path):
        """Undo should delete a file that didn't exist at checkpoint time."""
        f = tmp_path / "new.py"
        mgr = UndoManager()
        # Checkpoint before file exists
        mgr.checkpoint(label="before", extra_files=[str(f)])
        # Create file and second checkpoint
        f.write_text("new content")
        mgr.checkpoint(label="after", extra_files=[str(f)])
        # Undo → file should be deleted
        mgr.undo()
        assert not f.exists()

    def test_undo_returns_restored_files(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("old")
        mgr = UndoManager()
        mgr.checkpoint(extra_files=[str(f)])
        f.write_text("new")
        mgr.checkpoint(extra_files=[str(f)])
        result = mgr.undo()
        assert str(f) in result.restored_files


class TestUndoManagerHistory:
    def test_list_history(self, tmp_path):
        mgr = UndoManager()
        mgr.checkpoint(label="first")
        mgr.checkpoint(label="second")
        history = mgr.list_history()
        assert len(history) == 2
        assert "first" in history[0]
        assert "second" in history[1]

    def test_clear_removes_all(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        mgr = UndoManager()
        mgr.checkpoint(extra_files=[str(f)])
        mgr.checkpoint(extra_files=[str(f)])
        mgr.undo()
        mgr.clear()
        assert not mgr.can_undo
        assert not mgr.can_redo
        assert mgr.list_history() == []

    def test_list_redo(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        mgr = UndoManager()
        mgr.checkpoint(label="v1", extra_files=[str(f)])
        f.write_text("y")
        mgr.checkpoint(label="v2", extra_files=[str(f)])
        mgr.undo()
        redo_list = mgr.list_redo()
        assert len(redo_list) == 1
        assert "v2" in redo_list[0]

    def test_checkpoint_file_convenience(self, tmp_path):
        f = tmp_path / "x.py"
        f.write_text("hello")
        mgr = UndoManager()
        cp = mgr.checkpoint_file(str(f), label="saved")
        assert str(f) in cp.snapshots
        assert cp.label == "saved"
