"""Tests for lidco.conversation.branch_tree — BranchTree."""
from __future__ import annotations

import unittest

from lidco.conversation.branch_tree import BranchNode, BranchTree


class TestBranchNodeDataclass(unittest.TestCase):
    def test_frozen(self):
        n = BranchNode(id="a", parent_id=None, messages=(), created_at="2024-01-01", metadata={})
        self.assertEqual(n.id, "a")
        self.assertIsNone(n.parent_id)


class TestBranchTreeBasics(unittest.TestCase):
    def setUp(self):
        self.tree = BranchTree()

    def test_empty_tree(self):
        self.assertIsNone(self.tree.root())
        self.assertEqual(self.tree.all_branches(), [])
        self.assertEqual(self.tree.leaves(), [])

    def test_add_root(self):
        bid = self.tree.add_branch(None, [{"role": "user", "content": "hi"}])
        self.assertIsNotNone(bid)
        self.assertEqual(len(bid), 8)
        root = self.tree.root()
        self.assertIsNotNone(root)
        self.assertEqual(root.id, bid)

    def test_add_child(self):
        root_id = self.tree.add_branch(None, [{"role": "user"}])
        child_id = self.tree.add_branch(root_id, [{"role": "assistant"}])
        children = self.tree.get_children(root_id)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].id, child_id)

    def test_add_child_invalid_parent(self):
        with self.assertRaises(KeyError):
            self.tree.add_branch("nonexistent", [])

    def test_get_branch(self):
        bid = self.tree.add_branch(None, [{"role": "user"}])
        node = self.tree.get_branch(bid)
        self.assertIsNotNone(node)
        self.assertEqual(node.id, bid)

    def test_get_branch_nonexistent(self):
        self.assertIsNone(self.tree.get_branch("nope"))

    def test_get_parent(self):
        root_id = self.tree.add_branch(None, [])
        child_id = self.tree.add_branch(root_id, [])
        parent = self.tree.get_parent(child_id)
        self.assertEqual(parent.id, root_id)

    def test_get_parent_of_root(self):
        root_id = self.tree.add_branch(None, [])
        self.assertIsNone(self.tree.get_parent(root_id))

    def test_depth(self):
        root_id = self.tree.add_branch(None, [])
        child_id = self.tree.add_branch(root_id, [])
        grand_id = self.tree.add_branch(child_id, [])
        self.assertEqual(self.tree.depth(root_id), 0)
        self.assertEqual(self.tree.depth(child_id), 1)
        self.assertEqual(self.tree.depth(grand_id), 2)

    def test_depth_nonexistent(self):
        self.assertEqual(self.tree.depth("nope"), -1)

    def test_leaves(self):
        root_id = self.tree.add_branch(None, [])
        c1 = self.tree.add_branch(root_id, [])
        c2 = self.tree.add_branch(root_id, [])
        leaves = self.tree.leaves()
        leaf_ids = {l.id for l in leaves}
        self.assertEqual(leaf_ids, {c1, c2})

    def test_all_branches(self):
        r = self.tree.add_branch(None, [])
        c = self.tree.add_branch(r, [])
        self.assertEqual(len(self.tree.all_branches()), 2)

    def test_to_dict(self):
        r = self.tree.add_branch(None, [{"role": "user"}])
        d = self.tree.to_dict()
        self.assertIn("nodes", d)
        self.assertIn("children", d)
        self.assertIn(r, d["nodes"])

    def test_remove_branch(self):
        r = self.tree.add_branch(None, [])
        self.assertTrue(self.tree.remove_branch(r))
        self.assertIsNone(self.tree.get_branch(r))

    def test_remove_nonexistent(self):
        self.assertFalse(self.tree.remove_branch("nope"))

    def test_messages_are_tuple(self):
        r = self.tree.add_branch(None, [{"role": "user"}])
        node = self.tree.get_branch(r)
        self.assertIsInstance(node.messages, tuple)

    def test_metadata_default(self):
        r = self.tree.add_branch(None, [])
        node = self.tree.get_branch(r)
        self.assertEqual(node.metadata, {})

    def test_metadata_custom(self):
        r = self.tree.add_branch(None, [], metadata={"tag": "test"})
        node = self.tree.get_branch(r)
        self.assertEqual(node.metadata["tag"], "test")


if __name__ == "__main__":
    unittest.main()
