"""Tests for GitActionsProvider."""
from __future__ import annotations

import unittest

from lidco.actions.git_provider import GitAction, GitActionResult, GitActionsProvider


class TestGitAction(unittest.TestCase):
    def test_defaults(self):
        a = GitAction(action="stage", target=".")
        self.assertEqual(a.args, {})

    def test_frozen(self):
        a = GitAction(action="stage", target=".")
        with self.assertRaises(AttributeError):
            a.action = "commit"  # type: ignore[misc]


class TestGitActionsProvider(unittest.TestCase):
    def setUp(self):
        self.prov = GitActionsProvider()

    def test_stage(self):
        r = self.prov.stage(["a.py", "b.py"])
        self.assertTrue(r.success)
        self.assertIn("2 file(s)", r.message)
        self.assertIn("git add", r.command)

    def test_unstage(self):
        r = self.prov.unstage(["a.py"])
        self.assertTrue(r.success)
        self.assertIn("1 file(s)", r.message)
        self.assertIn("restore", r.command)

    def test_commit(self):
        r = self.prov.commit("fix bug")
        self.assertTrue(r.success)
        self.assertIn("fix bug", r.message)
        self.assertIn("commit", r.command)

    def test_push(self):
        r = self.prov.push()
        self.assertTrue(r.success)
        self.assertIn("origin", r.message)

    def test_push_with_branch(self):
        r = self.prov.push("origin", "feature")
        self.assertIn("feature", r.command)

    def test_create_branch(self):
        r = self.prov.create_branch("feat/new")
        self.assertTrue(r.success)
        self.assertIn("feat/new", r.message)

    def test_stash(self):
        r = self.prov.stash("wip")
        self.assertTrue(r.success)
        self.assertIn("wip", r.message)

    def test_stash_no_message(self):
        r = self.prov.stash()
        self.assertTrue(r.success)
        self.assertIn("Stashed", r.message)

    def test_stash_pop(self):
        r = self.prov.stash_pop()
        self.assertTrue(r.success)
        self.assertIn("Popped", r.message)

    def test_history(self):
        self.prov.stage(["a.py"])
        self.prov.commit("msg")
        hist = self.prov.history()
        self.assertEqual(len(hist), 2)

    def test_summary(self):
        self.prov.stage(["x.py"])
        self.prov.commit("init")
        s = self.prov.summary()
        self.assertEqual(s["total_actions"], 2)
        self.assertIn("stage", s["action_types"])
        self.assertIn("commit", s["action_types"])


if __name__ == "__main__":
    unittest.main()
