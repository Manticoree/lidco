"""Tests for lidco.conversation.branch_navigator — BranchNavigator."""
from __future__ import annotations

import unittest

from lidco.conversation.branch_tree import BranchTree
from lidco.conversation.branch_navigator import BranchNavigator


class TestNavigatorBasics(unittest.TestCase):
    def setUp(self):
        self.tree = BranchTree()
        self.root_id = self.tree.add_branch(None, [{"role": "user", "content": "root"}])
        self.child_id = self.tree.add_branch(self.root_id, [{"role": "assistant", "content": "child"}])
        self.nav = BranchNavigator(self.tree)

    def test_current_starts_at_root(self):
        self.assertIsNotNone(self.nav.current)
        self.assertEqual(self.nav.current.id, self.root_id)

    def test_jump(self):
        self.assertTrue(self.nav.jump(self.child_id))
        self.assertEqual(self.nav.current.id, self.child_id)

    def test_jump_invalid(self):
        self.assertFalse(self.nav.jump("nope"))

    def test_back(self):
        self.nav.jump(self.child_id)
        self.assertTrue(self.nav.back())
        self.assertEqual(self.nav.current.id, self.root_id)

    def test_back_at_root(self):
        self.assertFalse(self.nav.back())

    def test_forward(self):
        self.assertTrue(self.nav.forward())
        self.assertEqual(self.nav.current.id, self.child_id)

    def test_forward_no_children(self):
        self.nav.jump(self.child_id)
        self.assertFalse(self.nav.forward())

    def test_forward_invalid_index(self):
        self.assertFalse(self.nav.forward(child_index=99))

    def test_breadcrumb(self):
        self.nav.jump(self.child_id)
        bc = self.nav.breadcrumb()
        self.assertEqual(bc, [self.root_id, self.child_id])

    def test_breadcrumb_at_root(self):
        bc = self.nav.breadcrumb()
        self.assertEqual(bc, [self.root_id])


class TestNavigatorDisplay(unittest.TestCase):
    def test_display_tree(self):
        tree = BranchTree()
        r = tree.add_branch(None, [{"role": "user"}])
        c = tree.add_branch(r, [{"role": "assistant"}])
        nav = BranchNavigator(tree)
        display = nav.display_tree()
        self.assertIn(r, display)
        self.assertIn(c, display)
        self.assertIn("(*)", display)

    def test_display_empty_tree(self):
        nav = BranchNavigator(BranchTree())
        self.assertEqual(nav.display_tree(), "(empty tree)")


class TestNavigatorSearch(unittest.TestCase):
    def test_search_found(self):
        tree = BranchTree()
        r = tree.add_branch(None, [{"role": "user", "content": "hello world"}])
        tree.add_branch(r, [{"role": "assistant", "content": "goodbye"}])
        nav = BranchNavigator(tree)
        results = nav.search("hello")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, r)

    def test_search_case_insensitive(self):
        tree = BranchTree()
        tree.add_branch(None, [{"role": "user", "content": "Hello World"}])
        nav = BranchNavigator(tree)
        self.assertEqual(len(nav.search("hello")), 1)

    def test_search_not_found(self):
        tree = BranchTree()
        tree.add_branch(None, [{"role": "user", "content": "hi"}])
        nav = BranchNavigator(tree)
        self.assertEqual(nav.search("xyz"), [])


class TestNavigatorEmpty(unittest.TestCase):
    def test_empty_tree_current_none(self):
        nav = BranchNavigator(BranchTree())
        self.assertIsNone(nav.current)

    def test_empty_tree_breadcrumb(self):
        nav = BranchNavigator(BranchTree())
        self.assertEqual(nav.breadcrumb(), [])


if __name__ == "__main__":
    unittest.main()
