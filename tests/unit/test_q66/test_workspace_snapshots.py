"""Tests for WorkspaceSnapshotManager — T449."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("lidco.workspace.snapshot", reason="snapshot.py v1 removed in Q157")
from lidco.workspace.snapshot import RestoreResult, WorkspaceSnapshot, WorkspaceSnapshotManager


class TestWorkspaceSnapshotManager:
    def test_save_and_list(self, tmp_path):
        mgr = WorkspaceSnapshotManager(project_dir=tmp_path)
        snap = mgr.save("v1", history=[], files=[])
        snaps = mgr.list()
        assert len(snaps) == 1
        assert snaps[0].name == "v1"

    def test_save_captures_files(self, tmp_path):
        (tmp_path / "a.py").write_text("hello")
        mgr = WorkspaceSnapshotManager(project_dir=tmp_path)
        snap = mgr.save("s1", files=["a.py"])
        assert snap.files["a.py"] == "hello"

    def test_restore_by_name(self, tmp_path):
        f = tmp_path / "b.py"
        f.write_text("original")
        mgr = WorkspaceSnapshotManager(project_dir=tmp_path)
        mgr.save("snap1", files=["b.py"])
        f.write_text("modified")
        result = mgr.restore("snap1")
        assert result.success
        assert f.read_text() == "original"
        assert "b.py" in result.restored_files

    def test_restore_by_id(self, tmp_path):
        (tmp_path / "c.py").write_text("c_content")
        mgr = WorkspaceSnapshotManager(project_dir=tmp_path)
        snap = mgr.save("mysnap", files=["c.py"])
        (tmp_path / "c.py").write_text("changed")
        result = mgr.restore(snap.id)
        assert result.success
        assert (tmp_path / "c.py").read_text() == "c_content"

    def test_restore_not_found(self, tmp_path):
        mgr = WorkspaceSnapshotManager(project_dir=tmp_path)
        result = mgr.restore("nonexistent")
        assert not result.success
        assert result.error is not None

    def test_delete_by_name(self, tmp_path):
        mgr = WorkspaceSnapshotManager(project_dir=tmp_path)
        mgr.save("to_delete", files=[])
        assert len(mgr.list()) == 1
        mgr.delete("to_delete")
        assert len(mgr.list()) == 0

    def test_delete_not_found(self, tmp_path):
        mgr = WorkspaceSnapshotManager(project_dir=tmp_path)
        assert not mgr.delete("nope")

    def test_list_sorted_newest_first(self, tmp_path):
        mgr = WorkspaceSnapshotManager(project_dir=tmp_path)
        mgr.save("a", files=[])
        mgr.save("b", files=[])
        mgr.save("c", files=[])
        names = [s.name for s in mgr.list()]
        # Newest first — c was saved last
        assert names[0] == "c"

    def test_save_history(self, tmp_path):
        mgr = WorkspaceSnapshotManager(project_dir=tmp_path)
        history = [{"role": "user", "content": "hi"}]
        snap = mgr.save("with_hist", history=history)
        assert snap.history == history

    def test_snapshot_persisted_as_json(self, tmp_path):
        mgr = WorkspaceSnapshotManager(project_dir=tmp_path)
        snap = mgr.save("persisted", files=[])
        snap_path = tmp_path / ".lidco" / "workspace_snapshots" / f"{snap.id}.json"
        assert snap_path.exists()
        data = json.loads(snap_path.read_text())
        assert data["name"] == "persisted"

    def test_empty_list_when_no_dir(self, tmp_path):
        mgr = WorkspaceSnapshotManager(project_dir=tmp_path)
        assert mgr.list() == []
