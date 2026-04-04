"""Tests for CommitAmender (Q299)."""
import unittest

from lidco.smartgit.amender import CommitAmender, FixupEntry, SquashPlanEntry


class TestCommitAmender(unittest.TestCase):
    def setUp(self):
        self.amender = CommitAmender()

    # -- create_fixup ---------------------------------------------------

    def test_create_fixup_returns_id(self):
        fid = self.amender.create_fixup("abc123", "fix typo")
        self.assertIsInstance(fid, str)
        self.assertTrue(len(fid) > 0)

    def test_create_fixup_stores_entry(self):
        self.amender.create_fixup("abc123", "fix typo")
        self.assertEqual(len(self.amender.fixups), 1)
        self.assertEqual(self.amender.fixups[0].original_hash, "abc123")

    def test_create_fixup_message_prefix(self):
        self.amender.create_fixup("abc123", "fix typo")
        self.assertTrue(self.amender.fixups[0].message.startswith("fixup!"))

    def test_create_fixup_unique_ids(self):
        id1 = self.amender.create_fixup("aaa", "m1")
        id2 = self.amender.create_fixup("aaa", "m2")
        self.assertNotEqual(id1, id2)

    def test_fixups_returns_copy(self):
        self.amender.create_fixup("abc", "msg")
        copy = self.amender.fixups
        copy.clear()
        self.assertEqual(len(self.amender.fixups), 1)

    # -- can_amend / mark_amendable ------------------------------------

    def test_can_amend_false_by_default(self):
        self.assertFalse(self.amender.can_amend("abc123"))

    def test_can_amend_true_after_mark(self):
        self.amender.mark_amendable("abc123")
        self.assertTrue(self.amender.can_amend("abc123"))

    def test_can_amend_other_hash_still_false(self):
        self.amender.mark_amendable("abc123")
        self.assertFalse(self.amender.can_amend("def456"))

    # -- preserve_original ----------------------------------------------

    def test_preserve_original_returns_ref(self):
        ref = self.amender.preserve_original("abc12345")
        self.assertTrue(ref.startswith("refs/original/"))

    def test_preserve_original_retrievable(self):
        self.amender.preserve_original("abc12345")
        self.assertIsNotNone(self.amender.get_preserved("abc12345"))

    def test_get_preserved_none_if_missing(self):
        self.assertIsNone(self.amender.get_preserved("unknown"))

    # -- auto_squash_plan -----------------------------------------------

    def test_auto_squash_plan_all_pick(self):
        plan = self.amender.auto_squash_plan(["a", "b", "c"])
        actions = [e.action for e in plan]
        self.assertEqual(actions, ["pick", "pick", "pick"])

    def test_auto_squash_plan_with_fixup(self):
        self.amender.create_fixup("a", "fix a")
        plan = self.amender.auto_squash_plan(["a", "b"])
        actions = [e.action for e in plan]
        self.assertIn("fixup", actions)
        # fixup follows its target
        idx_pick = actions.index("pick")
        idx_fixup = actions.index("fixup")
        self.assertEqual(idx_fixup, idx_pick + 1)

    def test_auto_squash_plan_returns_squash_entries(self):
        plan = self.amender.auto_squash_plan(["x"])
        self.assertIsInstance(plan[0], SquashPlanEntry)

    def test_auto_squash_plan_empty_commits(self):
        plan = self.amender.auto_squash_plan([])
        self.assertEqual(plan, [])

    def test_auto_squash_plan_fixup_not_in_commits_ignored(self):
        self.amender.create_fixup("z", "fix z")
        plan = self.amender.auto_squash_plan(["a", "b"])
        actions = [e.action for e in plan]
        self.assertNotIn("fixup", actions)


if __name__ == "__main__":
    unittest.main()
