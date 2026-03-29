"""Tests for src/lidco/memory/approval_queue.py."""
import json
import os
import tempfile

from lidco.memory.approval_queue import (
    MemoryApprovalQueue,
    PendingFact,
    FactNotFoundError,
)
from lidco.memory.conversation_extractor import ExtractedFact


def _tmp_path():
    d = tempfile.mkdtemp()
    return os.path.join(d, "queue.json")


def _fact(content="test fact", confidence=0.7, tags=None):
    return ExtractedFact(content=content, confidence=confidence, tags=tags or [])


class TestPendingFact:
    def test_to_dict(self):
        f = _fact("hello", 0.8, ["python"])
        pf = PendingFact(id="abc", fact=f, created_at="2026-01-01T00:00:00")
        d = pf.to_dict()
        assert d["id"] == "abc"
        assert d["fact"]["content"] == "hello"
        assert d["created_at"] == "2026-01-01T00:00:00"

    def test_from_dict(self):
        d = {
            "id": "xyz",
            "fact": {"content": "hi", "confidence": 0.5, "tags": [], "source_turn": 0},
            "created_at": "2026-01-01",
        }
        pf = PendingFact.from_dict(d)
        assert pf.id == "xyz"
        assert pf.fact.content == "hi"

    def test_roundtrip(self):
        f = _fact("roundtrip", 0.9)
        pf = PendingFact(id="rt", fact=f, created_at="2026-03-01")
        d = pf.to_dict()
        pf2 = PendingFact.from_dict(d)
        assert pf2.id == pf.id
        assert pf2.fact.content == pf.fact.content


class TestMemoryApprovalQueue:
    def test_add_returns_id(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        fid = q.add(_fact())
        assert isinstance(fid, str)
        assert len(fid) > 0

    def test_add_persists(self):
        path = _tmp_path()
        q = MemoryApprovalQueue(storage_path=path)
        q.add(_fact("persisted"))
        q2 = MemoryApprovalQueue(storage_path=path)
        assert q2.count() == 1

    def test_list_pending_empty(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        assert q.list_pending() == []

    def test_list_pending_returns_added(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        q.add(_fact("a"))
        q.add(_fact("b"))
        pending = q.list_pending()
        assert len(pending) == 2

    def test_approve_returns_fact(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        fid = q.add(_fact("approve me"))
        fact = q.approve(fid)
        assert fact.content == "approve me"
        assert q.count() == 0

    def test_approve_missing_raises(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        try:
            q.approve("nonexistent")
            assert False, "Expected FactNotFoundError"
        except FactNotFoundError:
            pass

    def test_reject_removes(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        fid = q.add(_fact("reject me"))
        q.reject(fid)
        assert q.count() == 0

    def test_reject_missing_raises(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        try:
            q.reject("nonexistent")
            assert False, "Expected FactNotFoundError"
        except FactNotFoundError:
            pass

    def test_auto_approve_threshold(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        q.add(_fact("low", 0.5))
        q.add(_fact("high", 0.95))
        q.add(_fact("mid", 0.89))
        approved = q.auto_approve(threshold=0.9)
        assert len(approved) == 1
        assert approved[0].content == "high"
        assert q.count() == 2

    def test_auto_approve_all(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        q.add(_fact("a", 0.95))
        q.add(_fact("b", 0.91))
        approved = q.auto_approve(threshold=0.9)
        assert len(approved) == 2
        assert q.count() == 0

    def test_auto_approve_none(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        q.add(_fact("low", 0.3))
        approved = q.auto_approve(threshold=0.9)
        assert approved == []
        assert q.count() == 1

    def test_count(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        assert q.count() == 0
        q.add(_fact())
        assert q.count() == 1
        q.add(_fact())
        assert q.count() == 2

    def test_get_existing(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        fid = q.add(_fact("findme"))
        pf = q.get(fid)
        assert pf is not None
        assert pf.fact.content == "findme"

    def test_get_missing(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        assert q.get("nope") is None

    def test_clear(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        q.add(_fact())
        q.add(_fact())
        removed = q.clear()
        assert removed == 2
        assert q.count() == 0

    def test_clear_empty(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        assert q.clear() == 0

    def test_load_corrupt_json(self):
        path = _tmp_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("{corrupt json!!!")
        q = MemoryApprovalQueue(storage_path=path)
        assert q.count() == 0

    def test_load_nonexistent_file(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        assert q.count() == 0

    def test_multiple_add_unique_ids(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        ids = [q.add(_fact(f"fact{i}")) for i in range(10)]
        assert len(set(ids)) == 10

    def test_pending_has_created_at(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        q.add(_fact())
        pending = q.list_pending()
        assert pending[0].created_at is not None
        assert len(pending[0].created_at) > 0

    def test_approve_then_list(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        fid = q.add(_fact("only"))
        q.approve(fid)
        assert q.list_pending() == []

    def test_reject_then_list(self):
        q = MemoryApprovalQueue(storage_path=_tmp_path())
        fid = q.add(_fact("only"))
        q.reject(fid)
        assert q.list_pending() == []

    def test_persistence_after_approve(self):
        path = _tmp_path()
        q = MemoryApprovalQueue(storage_path=path)
        fid = q.add(_fact("x"))
        q.approve(fid)
        q2 = MemoryApprovalQueue(storage_path=path)
        assert q2.count() == 0

    def test_persistence_after_reject(self):
        path = _tmp_path()
        q = MemoryApprovalQueue(storage_path=path)
        fid = q.add(_fact("x"))
        q.reject(fid)
        q2 = MemoryApprovalQueue(storage_path=path)
        assert q2.count() == 0
