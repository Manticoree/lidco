"""Tests for lidco.checkpoint.manager — Q160 Task 914."""

from __future__ import annotations

import unittest

from lidco.checkpoint.manager import Checkpoint, CheckpointManager, RewindResult


class TestCheckpoint(unittest.TestCase):
    def test_dataclass_fields(self):
        cp = Checkpoint(
            checkpoint_id="abc123",
            timestamp=1000.0,
            file_snapshots={"a.py": "x"},
            conversation_length=5,
            label="v1",
        )
        self.assertEqual(cp.checkpoint_id, "abc123")
        self.assertAlmostEqual(cp.timestamp, 1000.0)
        self.assertEqual(cp.file_snapshots, {"a.py": "x"})
        self.assertEqual(cp.conversation_length, 5)
        self.assertEqual(cp.label, "v1")

    def test_default_label(self):
        cp = Checkpoint(
            checkpoint_id="x", timestamp=0.0, file_snapshots={}, conversation_length=0,
        )
        self.assertEqual(cp.label, "")


class TestRewindResult(unittest.TestCase):
    def test_fields(self):
        r = RewindResult(restored_files=["a.py"], conversation_truncate_to=3, success=True)
        self.assertTrue(r.success)
        self.assertEqual(r.restored_files, ["a.py"])
        self.assertEqual(r.conversation_truncate_to, 3)


class TestCheckpointManager(unittest.TestCase):
    def setUp(self):
        self.mgr = CheckpointManager(max_checkpoints=5)

    # -- create -------------------------------------------------------------

    def test_create_returns_checkpoint(self):
        cp = self.mgr.create({"a.py": "hello"}, 10, label="first")
        self.assertIsInstance(cp, Checkpoint)
        self.assertEqual(cp.label, "first")
        self.assertEqual(cp.conversation_length, 10)
        self.assertEqual(cp.file_snapshots, {"a.py": "hello"})
        self.assertTrue(len(cp.checkpoint_id) > 0)

    def test_create_generates_unique_ids(self):
        ids = {self.mgr.create({}, 0).checkpoint_id for _ in range(10)}
        self.assertEqual(len(ids), 10)

    def test_create_default_label(self):
        cp = self.mgr.create({}, 0)
        self.assertEqual(cp.label, "")

    # -- list ---------------------------------------------------------------

    def test_list_empty(self):
        self.assertEqual(self.mgr.list(), [])

    def test_list_returns_ordered(self):
        c1 = self.mgr.create({}, 1, "a")
        c2 = self.mgr.create({}, 2, "b")
        self.assertEqual([c.checkpoint_id for c in self.mgr.list()],
                         [c1.checkpoint_id, c2.checkpoint_id])

    # -- get ----------------------------------------------------------------

    def test_get_existing(self):
        cp = self.mgr.create({}, 1)
        self.assertEqual(self.mgr.get(cp.checkpoint_id), cp)

    def test_get_missing(self):
        self.assertIsNone(self.mgr.get("nonexistent"))

    # -- eviction -----------------------------------------------------------

    def test_eviction_at_max(self):
        for i in range(7):
            self.mgr.create({}, i)
        self.assertEqual(len(self.mgr), 5)

    def test_oldest_evicted_first(self):
        cps = [self.mgr.create({}, i) for i in range(7)]
        ids = {cp.checkpoint_id for cp in self.mgr.list()}
        # First two should be evicted
        self.assertNotIn(cps[0].checkpoint_id, ids)
        self.assertNotIn(cps[1].checkpoint_id, ids)
        self.assertIn(cps[6].checkpoint_id, ids)

    # -- rewind_to ----------------------------------------------------------

    def test_rewind_to_code(self):
        written: dict[str, str] = {}
        mgr = CheckpointManager(write_fn=lambda p, c: written.__setitem__(p, c))
        cp = mgr.create({"f.py": "content"}, 5)
        r = mgr.rewind_to(cp.checkpoint_id, mode="code")
        self.assertTrue(r.success)
        self.assertEqual(r.restored_files, ["f.py"])
        self.assertIsNone(r.conversation_truncate_to)
        self.assertEqual(written, {"f.py": "content"})

    def test_rewind_to_chat(self):
        cp = self.mgr.create({"a.py": "x"}, 42)
        r = self.mgr.rewind_to(cp.checkpoint_id, mode="chat")
        self.assertTrue(r.success)
        self.assertEqual(r.conversation_truncate_to, 42)
        self.assertEqual(r.restored_files, [])

    def test_rewind_to_both(self):
        cp = self.mgr.create({"b.py": "y"}, 10)
        r = self.mgr.rewind_to(cp.checkpoint_id, mode="both")
        self.assertTrue(r.success)
        self.assertEqual(r.conversation_truncate_to, 10)
        # Without write_fn, restored_files = keys
        self.assertEqual(r.restored_files, ["b.py"])

    def test_rewind_to_missing(self):
        r = self.mgr.rewind_to("nope")
        self.assertFalse(r.success)

    # -- fork ---------------------------------------------------------------

    def test_fork_creates_copy(self):
        cp = self.mgr.create({"x.py": "code"}, 5, label="orig")
        forked = self.mgr.fork(cp.checkpoint_id)
        self.assertNotEqual(forked.checkpoint_id, cp.checkpoint_id)
        self.assertEqual(forked.file_snapshots, cp.file_snapshots)
        self.assertEqual(forked.conversation_length, cp.conversation_length)
        self.assertIn("fork of", forked.label)

    def test_fork_missing_raises(self):
        with self.assertRaises(KeyError):
            self.mgr.fork("nonexistent")

    # -- clear / len --------------------------------------------------------

    def test_clear(self):
        self.mgr.create({}, 0)
        self.mgr.create({}, 1)
        self.mgr.clear()
        self.assertEqual(len(self.mgr), 0)

    def test_len(self):
        self.assertEqual(len(self.mgr), 0)
        self.mgr.create({}, 0)
        self.assertEqual(len(self.mgr), 1)

    # -- files dict is a copy -----------------------------------------------

    def test_file_snapshots_are_copied(self):
        files = {"a.py": "v1"}
        cp = self.mgr.create(files, 0)
        files["a.py"] = "v2"
        self.assertEqual(cp.file_snapshots["a.py"], "v1")


if __name__ == "__main__":
    unittest.main()
