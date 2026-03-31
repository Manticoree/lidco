"""Tests for lidco.checkpoint.rewind — Q160 Task 915."""

from __future__ import annotations

import unittest

from lidco.checkpoint.manager import CheckpointManager
from lidco.checkpoint.rewind import RewindEngine


class TestRewindEngine(unittest.TestCase):
    def setUp(self):
        self.mgr = CheckpointManager()
        self.engine = RewindEngine(self.mgr)

    # -- rewind_code --------------------------------------------------------

    def test_rewind_code_restores_files(self):
        cp = self.mgr.create({"a.py": "aaa", "b.py": "bbb"}, 5)
        written: dict[str, str] = {}
        restored = self.engine.rewind_code(cp.checkpoint_id, lambda p, c: written.__setitem__(p, c))
        self.assertEqual(set(restored), {"a.py", "b.py"})
        self.assertEqual(written, {"a.py": "aaa", "b.py": "bbb"})

    def test_rewind_code_missing_checkpoint(self):
        restored = self.engine.rewind_code("nope", lambda p, c: None)
        self.assertEqual(restored, [])

    def test_rewind_code_empty_files(self):
        cp = self.mgr.create({}, 0)
        restored = self.engine.rewind_code(cp.checkpoint_id, lambda p, c: None)
        self.assertEqual(restored, [])

    # -- rewind_chat --------------------------------------------------------

    def test_rewind_chat_returns_position(self):
        cp = self.mgr.create({}, 42)
        pos = self.engine.rewind_chat(cp.checkpoint_id)
        self.assertEqual(pos, 42)

    def test_rewind_chat_missing(self):
        pos = self.engine.rewind_chat("nonexistent")
        self.assertEqual(pos, -1)

    # -- rewind_both --------------------------------------------------------

    def test_rewind_both_success(self):
        cp = self.mgr.create({"x.py": "hello"}, 10)
        written: dict[str, str] = {}
        result = self.engine.rewind_both(cp.checkpoint_id, lambda p, c: written.__setitem__(p, c))
        self.assertTrue(result.success)
        self.assertEqual(result.restored_files, ["x.py"])
        self.assertEqual(result.conversation_truncate_to, 10)
        self.assertEqual(written, {"x.py": "hello"})

    def test_rewind_both_missing(self):
        result = self.engine.rewind_both("nope", lambda p, c: None)
        self.assertFalse(result.success)

    # -- diff_from_checkpoint -----------------------------------------------

    def test_diff_no_changes(self):
        cp = self.mgr.create({"a.py": "same"}, 0)
        diffs = self.engine.diff_from_checkpoint(cp.checkpoint_id, {"a.py": "same"})
        self.assertEqual(diffs, {})

    def test_diff_modified_file(self):
        cp = self.mgr.create({"a.py": "old\n"}, 0)
        diffs = self.engine.diff_from_checkpoint(cp.checkpoint_id, {"a.py": "new\n"})
        self.assertIn("a.py", diffs)
        self.assertIn("-old", diffs["a.py"])
        self.assertIn("+new", diffs["a.py"])

    def test_diff_added_file(self):
        cp = self.mgr.create({}, 0)
        diffs = self.engine.diff_from_checkpoint(cp.checkpoint_id, {"new.py": "code\n"})
        self.assertIn("new.py", diffs)
        self.assertIn("+code", diffs["new.py"])

    def test_diff_deleted_file(self):
        cp = self.mgr.create({"old.py": "code\n"}, 0)
        diffs = self.engine.diff_from_checkpoint(cp.checkpoint_id, {})
        self.assertIn("old.py", diffs)
        self.assertIn("-code", diffs["old.py"])

    def test_diff_missing_checkpoint(self):
        diffs = self.engine.diff_from_checkpoint("nope", {"a.py": "x"})
        self.assertEqual(diffs, {})

    def test_diff_multiple_files(self):
        cp = self.mgr.create({"a.py": "a\n", "b.py": "b\n"}, 0)
        diffs = self.engine.diff_from_checkpoint(
            cp.checkpoint_id,
            {"a.py": "a2\n", "b.py": "b\n"},
        )
        self.assertIn("a.py", diffs)
        self.assertNotIn("b.py", diffs)  # unchanged


if __name__ == "__main__":
    unittest.main()
