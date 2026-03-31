"""Tests for BranchManager (Q165/Task 937)."""
from __future__ import annotations

import unittest

from lidco.session.branch_manager import Branch, BranchManager


class TestBranchDataclass(unittest.TestCase):
    def test_branch_fields(self):
        b = Branch(
            branch_id="abc",
            name="main",
            parent_id=None,
            created_at=1.0,
            conversation=[],
            file_snapshots={},
        )
        self.assertEqual(b.branch_id, "abc")
        self.assertEqual(b.name, "main")
        self.assertIsNone(b.parent_id)
        self.assertFalse(b.is_active)

    def test_branch_default_is_active(self):
        b = Branch("id", "n", None, 0.0, [], {})
        self.assertFalse(b.is_active)


class TestBranchManagerCreate(unittest.TestCase):
    def setUp(self):
        self.mgr = BranchManager(max_branches=5)

    def test_create_returns_branch(self):
        b = self.mgr.create("test", [{"role": "user", "content": "hi"}], {"f.py": "x"})
        self.assertIsInstance(b, Branch)
        self.assertEqual(b.name, "test")
        self.assertEqual(len(b.conversation), 1)
        self.assertEqual(b.file_snapshots["f.py"], "x")

    def test_create_assigns_unique_ids(self):
        b1 = self.mgr.create("a", [], {})
        b2 = self.mgr.create("b", [], {})
        self.assertNotEqual(b1.branch_id, b2.branch_id)

    def test_create_with_parent(self):
        b1 = self.mgr.create("parent", [], {})
        b2 = self.mgr.create("child", [], {}, parent_id=b1.branch_id)
        self.assertEqual(b2.parent_id, b1.branch_id)

    def test_create_copies_data(self):
        conv = [{"role": "user", "content": "hi"}]
        files = {"a.py": "code"}
        b = self.mgr.create("t", conv, files)
        conv.append({"role": "assistant", "content": "hello"})
        files["b.py"] = "more"
        self.assertEqual(len(b.conversation), 1)
        self.assertNotIn("b.py", b.file_snapshots)

    def test_create_exceeds_limit(self):
        for i in range(5):
            self.mgr.create(f"b{i}", [], {})
        with self.assertRaises(ValueError):
            self.mgr.create("overflow", [], {})


class TestBranchManagerSwitch(unittest.TestCase):
    def setUp(self):
        self.mgr = BranchManager()

    def test_switch_activates_branch(self):
        b = self.mgr.create("x", [], {})
        result = self.mgr.switch(b.branch_id)
        self.assertTrue(result.is_active)
        self.assertEqual(self.mgr.get_active(), result)

    def test_switch_deactivates_previous(self):
        b1 = self.mgr.create("a", [], {})
        b2 = self.mgr.create("b", [], {})
        self.mgr.switch(b1.branch_id)
        self.mgr.switch(b2.branch_id)
        self.assertFalse(b1.is_active)
        self.assertTrue(b2.is_active)

    def test_switch_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.mgr.switch("nonexistent")


class TestBranchManagerListDelete(unittest.TestCase):
    def setUp(self):
        self.mgr = BranchManager()

    def test_list_empty(self):
        self.assertEqual(self.mgr.list_branches(), [])

    def test_list_sorted_by_time(self):
        b1 = self.mgr.create("first", [], {})
        b2 = self.mgr.create("second", [], {})
        result = self.mgr.list_branches()
        self.assertEqual(len(result), 2)
        self.assertLessEqual(result[0].created_at, result[1].created_at)

    def test_delete_existing(self):
        b = self.mgr.create("x", [], {})
        self.assertTrue(self.mgr.delete(b.branch_id))
        self.assertIsNone(self.mgr.get(b.branch_id))

    def test_delete_missing(self):
        self.assertFalse(self.mgr.delete("nope"))

    def test_delete_active_clears_active(self):
        b = self.mgr.create("x", [], {})
        self.mgr.switch(b.branch_id)
        self.mgr.delete(b.branch_id)
        self.assertIsNone(self.mgr.get_active())

    def test_get_returns_branch(self):
        b = self.mgr.create("x", [], {})
        self.assertEqual(self.mgr.get(b.branch_id), b)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.mgr.get("nope"))

    def test_get_active_none_initially(self):
        self.assertIsNone(self.mgr.get_active())


if __name__ == "__main__":
    unittest.main()
