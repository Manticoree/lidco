"""Tests for src/lidco/memory/session_checkpoint.py."""
import json
import os
import tempfile

from lidco.memory.session_checkpoint import (
    SessionCheckpointStore,
    SessionCheckpoint,
    CheckpointDiff,
    CheckpointNotFoundError,
)


def _tmp_path():
    d = tempfile.mkdtemp()
    return os.path.join(d, "checkpoints.json")


class TestSessionCheckpoint:
    def test_to_dict(self):
        cp = SessionCheckpoint(
            id="a", label="test", created_at="2026-01-01",
            messages=[{"role": "user"}], file_refs=["f.py"],
            memory_snapshot=[{"content": "x"}],
        )
        d = cp.to_dict()
        assert d["id"] == "a"
        assert d["label"] == "test"
        assert len(d["messages"]) == 1
        assert d["file_refs"] == ["f.py"]

    def test_from_dict(self):
        d = {"id": "b", "label": "lbl", "created_at": "2026-01-01",
             "messages": [], "file_refs": [], "memory_snapshot": []}
        cp = SessionCheckpoint.from_dict(d)
        assert cp.id == "b"
        assert cp.label == "lbl"

    def test_from_dict_minimal(self):
        d = {"id": "c", "label": "x", "created_at": "2026-01-01"}
        cp = SessionCheckpoint.from_dict(d)
        assert cp.messages == []
        assert cp.file_refs == []

    def test_roundtrip(self):
        cp = SessionCheckpoint(id="r", label="round", created_at="2026-03-01",
                               messages=[{"a": 1}], file_refs=["x.py"])
        d = cp.to_dict()
        cp2 = SessionCheckpoint.from_dict(d)
        assert cp2.id == cp.id
        assert cp2.messages == cp.messages

    def test_default_fields(self):
        cp = SessionCheckpoint(id="d", label="def", created_at="now")
        assert cp.messages == []
        assert cp.file_refs == []
        assert cp.memory_snapshot == []


class TestCheckpointDiff:
    def test_fields(self):
        d = CheckpointDiff(messages_added=3, messages_removed=1, files_changed=["a.py"])
        assert d.messages_added == 3
        assert d.messages_removed == 1
        assert d.files_changed == ["a.py"]

    def test_default_files(self):
        d = CheckpointDiff(messages_added=0, messages_removed=0)
        assert d.files_changed == []


class TestSessionCheckpointStore:
    def test_save_returns_id(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        cp_id = store.save("label", [])
        assert isinstance(cp_id, str)
        assert len(cp_id) > 0

    def test_save_persists(self):
        path = _tmp_path()
        store = SessionCheckpointStore(storage_path=path)
        store.save("persisted", [{"role": "user"}])
        store2 = SessionCheckpointStore(storage_path=path)
        assert store2.count() == 1

    def test_list_empty(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        assert store.list() == []

    def test_list_returns_saved(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        store.save("a", [])
        store.save("b", [])
        cps = store.list()
        assert len(cps) == 2

    def test_restore_existing(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        cp_id = store.save("restore me", [{"msg": 1}], file_refs=["x.py"])
        cp = store.restore(cp_id)
        assert cp.label == "restore me"
        assert cp.messages == [{"msg": 1}]
        assert cp.file_refs == ["x.py"]

    def test_restore_missing_raises(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        try:
            store.restore("nonexistent")
            assert False, "Expected CheckpointNotFoundError"
        except CheckpointNotFoundError:
            pass

    def test_diff_messages_added(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        id1 = store.save("a", [{"m": 1}])
        id2 = store.save("b", [{"m": 1}, {"m": 2}])
        d = store.diff(id1, id2)
        assert d.messages_added == 1
        assert d.messages_removed == 0

    def test_diff_messages_removed(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        id1 = store.save("a", [{"m": 1}, {"m": 2}])
        id2 = store.save("b", [{"m": 1}])
        d = store.diff(id1, id2)
        assert d.messages_removed == 1

    def test_diff_files_changed(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        id1 = store.save("a", [], file_refs=["a.py", "b.py"])
        id2 = store.save("b", [], file_refs=["b.py", "c.py"])
        d = store.diff(id1, id2)
        assert sorted(d.files_changed) == ["a.py", "c.py"]

    def test_diff_identical(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        id1 = store.save("a", [{"x": 1}], file_refs=["a.py"])
        id2 = store.save("b", [{"x": 1}], file_refs=["a.py"])
        d = store.diff(id1, id2)
        assert d.messages_added == 0
        assert d.messages_removed == 0
        assert d.files_changed == []

    def test_diff_missing_id1_raises(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        id2 = store.save("b", [])
        try:
            store.diff("bad", id2)
            assert False, "Expected CheckpointNotFoundError"
        except CheckpointNotFoundError:
            pass

    def test_diff_missing_id2_raises(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        id1 = store.save("a", [])
        try:
            store.diff(id1, "bad")
            assert False, "Expected CheckpointNotFoundError"
        except CheckpointNotFoundError:
            pass

    def test_delete(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        cp_id = store.save("del", [])
        store.delete(cp_id)
        assert store.count() == 0

    def test_delete_missing_raises(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        try:
            store.delete("nonexistent")
            assert False, "Expected CheckpointNotFoundError"
        except CheckpointNotFoundError:
            pass

    def test_count(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        assert store.count() == 0
        store.save("a", [])
        assert store.count() == 1
        store.save("b", [])
        assert store.count() == 2

    def test_get_existing(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        cp_id = store.save("get me", [])
        cp = store.get(cp_id)
        assert cp is not None
        assert cp.label == "get me"

    def test_get_missing(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        assert store.get("nope") is None

    def test_clear(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        store.save("a", [])
        store.save("b", [])
        removed = store.clear()
        assert removed == 2
        assert store.count() == 0

    def test_clear_empty(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        assert store.clear() == 0

    def test_load_corrupt_json(self):
        path = _tmp_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("not json!!!")
        store = SessionCheckpointStore(storage_path=path)
        assert store.count() == 0

    def test_load_nonexistent_file(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        assert store.count() == 0

    def test_save_with_memory_snapshot(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        cp_id = store.save("snap", [], memory_snapshot=[{"fact": "x"}])
        cp = store.restore(cp_id)
        assert cp.memory_snapshot == [{"fact": "x"}]

    def test_save_none_file_refs(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        cp_id = store.save("none refs", [], file_refs=None)
        cp = store.restore(cp_id)
        assert cp.file_refs == []

    def test_save_none_memory_snapshot(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        cp_id = store.save("none snap", [], memory_snapshot=None)
        cp = store.restore(cp_id)
        assert cp.memory_snapshot == []

    def test_multiple_save_unique_ids(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        ids = [store.save(f"cp{i}", []) for i in range(10)]
        assert len(set(ids)) == 10

    def test_delete_persists(self):
        path = _tmp_path()
        store = SessionCheckpointStore(storage_path=path)
        cp_id = store.save("del persist", [])
        store.delete(cp_id)
        store2 = SessionCheckpointStore(storage_path=path)
        assert store2.count() == 0

    def test_list_ordered_by_created_at(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        store.save("first", [])
        store.save("second", [])
        cps = store.list()
        assert cps[0].created_at <= cps[1].created_at

    def test_diff_empty_checkpoints(self):
        store = SessionCheckpointStore(storage_path=_tmp_path())
        id1 = store.save("a", [])
        id2 = store.save("b", [])
        d = store.diff(id1, id2)
        assert d.messages_added == 0
        assert d.messages_removed == 0
        assert d.files_changed == []
