"""Tests for SessionSync — Q189, task 1059."""
from __future__ import annotations

import unittest

from lidco.remote.session_sync import SessionSync, SyncOp, SyncOpKind, SyncResult


class TestSyncOp(unittest.TestCase):
    def test_frozen(self):
        op = SyncOp(kind=SyncOpKind.ADD, key="k", value="v")
        with self.assertRaises(AttributeError):
            op.key = "x"  # type: ignore[misc]

    def test_fields(self):
        op = SyncOp(kind=SyncOpKind.REMOVE, key="a")
        self.assertEqual(op.kind, SyncOpKind.REMOVE)
        self.assertEqual(op.key, "a")
        self.assertIsNone(op.value)


class TestSyncResult(unittest.TestCase):
    def test_frozen(self):
        sr = SyncResult(merged={"a": 1}, conflicts=("a",))
        with self.assertRaises(AttributeError):
            sr.merged = {}  # type: ignore[misc]

    def test_fields(self):
        sr = SyncResult(merged={}, conflicts=())
        self.assertEqual(sr.merged, {})
        self.assertEqual(sr.conflicts, ())


class TestSyncOpKind(unittest.TestCase):
    def test_values(self):
        self.assertEqual(SyncOpKind.ADD.value, "add")
        self.assertEqual(SyncOpKind.REMOVE.value, "remove")
        self.assertEqual(SyncOpKind.UPDATE.value, "update")


class TestSessionSync(unittest.TestCase):
    def test_session_id(self):
        ss = SessionSync("sess-1")
        self.assertEqual(ss.session_id, "sess-1")

    def test_sync_no_conflict(self):
        ss = SessionSync("s")
        result = ss.sync_state({"a": 1}, {"b": 2})
        self.assertEqual(result.merged, {"a": 1, "b": 2})
        self.assertEqual(result.conflicts, ())

    def test_sync_same_values(self):
        ss = SessionSync("s")
        result = ss.sync_state({"x": 10}, {"x": 10})
        self.assertEqual(result.merged, {"x": 10})
        self.assertEqual(result.conflicts, ())

    def test_sync_conflict_local_wins(self):
        ss = SessionSync("s")
        result = ss.sync_state({"k": "local"}, {"k": "remote"})
        self.assertEqual(result.merged["k"], "local")
        self.assertIn("k", result.conflicts)

    def test_sync_empty(self):
        ss = SessionSync("s")
        result = ss.sync_state({}, {})
        self.assertEqual(result.merged, {})
        self.assertEqual(result.conflicts, ())

    def test_resolve_local_wins(self):
        ss = SessionSync("s")
        r = ss.resolve_conflict("L", "R", strategy="local_wins")
        self.assertEqual(r, {"resolved": "L"})

    def test_resolve_remote_wins(self):
        ss = SessionSync("s")
        r = ss.resolve_conflict("L", "R", strategy="remote_wins")
        self.assertEqual(r, {"resolved": "R"})

    def test_resolve_merge_dicts(self):
        ss = SessionSync("s")
        r = ss.resolve_conflict({"a": 1}, {"b": 2}, strategy="merge")
        self.assertEqual(r, {"resolved": {"a": 1, "b": 2}})

    def test_resolve_merge_non_dict(self):
        ss = SessionSync("s")
        r = ss.resolve_conflict("L", "R", strategy="merge")
        self.assertEqual(r, {"resolved": "R"})

    def test_resolve_unknown_strategy(self):
        ss = SessionSync("s")
        with self.assertRaises(ValueError):
            ss.resolve_conflict("L", "R", strategy="unknown")

    def test_compute_diff_add(self):
        ss = SessionSync("s")
        ops = ss.compute_diff({}, {"a": 1})
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].kind, SyncOpKind.ADD)
        self.assertEqual(ops[0].key, "a")
        self.assertEqual(ops[0].value, 1)

    def test_compute_diff_remove(self):
        ss = SessionSync("s")
        ops = ss.compute_diff({"a": 1}, {})
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].kind, SyncOpKind.REMOVE)

    def test_compute_diff_update(self):
        ss = SessionSync("s")
        ops = ss.compute_diff({"a": 1}, {"a": 2})
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].kind, SyncOpKind.UPDATE)
        self.assertEqual(ops[0].value, 2)

    def test_compute_diff_no_change(self):
        ss = SessionSync("s")
        ops = ss.compute_diff({"a": 1}, {"a": 1})
        self.assertEqual(len(ops), 0)

    def test_compute_diff_returns_tuple(self):
        ss = SessionSync("s")
        ops = ss.compute_diff({}, {"x": 1})
        self.assertIsInstance(ops, tuple)

    def test_sync_result_conflicts_is_tuple(self):
        ss = SessionSync("s")
        result = ss.sync_state({"k": 1}, {"k": 2})
        self.assertIsInstance(result.conflicts, tuple)


if __name__ == "__main__":
    unittest.main()
