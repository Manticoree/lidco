"""Tests for MRWorkflow (Q290)."""

import unittest

from lidco.gitlab.mr_workflow import MRWorkflow, MR


class TestCreateMR(unittest.TestCase):
    def test_create_basic(self):
        wf = MRWorkflow()
        mr = wf.create_mr("feat: add login", "desc", "feature/login")
        self.assertIsInstance(mr, MR)
        self.assertEqual(mr.title, "feat: add login")
        self.assertEqual(mr.source_branch, "feature/login")
        self.assertEqual(mr.target_branch, "main")
        self.assertEqual(mr.state, "opened")

    def test_create_custom_target(self):
        wf = MRWorkflow()
        mr = wf.create_mr("fix", "", "hotfix", "develop")
        self.assertEqual(mr.target_branch, "develop")

    def test_empty_title_raises(self):
        wf = MRWorkflow()
        with self.assertRaises(ValueError):
            wf.create_mr("", "body", "src")

    def test_empty_source_raises(self):
        wf = MRWorkflow()
        with self.assertRaises(ValueError):
            wf.create_mr("title", "body", "")

    def test_same_branches_raises(self):
        wf = MRWorkflow()
        with self.assertRaises(ValueError):
            wf.create_mr("t", "b", "main", "main")

    def test_incremental_ids(self):
        wf = MRWorkflow()
        mr1 = wf.create_mr("a", "", "b1")
        mr2 = wf.create_mr("b", "", "b2")
        self.assertEqual(mr2.id, mr1.id + 1)


class TestAutoDescribe(unittest.TestCase):
    def test_empty_diff(self):
        wf = MRWorkflow()
        self.assertEqual(wf.auto_describe(""), "No changes detected.")
        self.assertEqual(wf.auto_describe("   "), "No changes detected.")

    def test_diff_counts(self):
        diff = "+added line\n-removed line\n context\n+another add"
        wf = MRWorkflow()
        desc = wf.auto_describe(diff)
        self.assertIn("2 additions", desc)
        self.assertIn("1 deletions", desc)


class TestAssignReviewers(unittest.TestCase):
    def test_assign_success(self):
        wf = MRWorkflow()
        mr = wf.create_mr("t", "", "src")
        result = wf.assign_reviewers(mr.id, ["alice", "bob"])
        self.assertTrue(result)
        self.assertEqual(wf._get_mr(mr.id).reviewers, ["alice", "bob"])

    def test_missing_mr_raises(self):
        wf = MRWorkflow()
        with self.assertRaises(KeyError):
            wf.assign_reviewers(999, ["a"])

    def test_empty_reviewers_raises(self):
        wf = MRWorkflow()
        mr = wf.create_mr("t", "", "src")
        with self.assertRaises(ValueError):
            wf.assign_reviewers(mr.id, [])


class TestApprove(unittest.TestCase):
    def test_approve_success(self):
        wf = MRWorkflow()
        mr = wf.create_mr("t", "", "src")
        self.assertTrue(wf.approve(mr.id))
        self.assertTrue(wf._get_mr(mr.id).approved)

    def test_approve_missing_raises(self):
        wf = MRWorkflow()
        with self.assertRaises(KeyError):
            wf.approve(999)

    def test_approve_closed_raises(self):
        wf = MRWorkflow()
        mr = wf.create_mr("t", "", "src")
        mr.state = "merged"
        with self.assertRaises(ValueError):
            wf.approve(mr.id)


class TestListDiscussions(unittest.TestCase):
    def test_empty_discussions(self):
        wf = MRWorkflow()
        mr = wf.create_mr("t", "", "src")
        self.assertEqual(wf.list_discussions(mr.id), [])

    def test_with_discussions(self):
        wf = MRWorkflow()
        mr = wf.create_mr("t", "", "src")
        mr.discussions.append({"body": "looks good"})
        self.assertEqual(len(wf.list_discussions(mr.id)), 1)

    def test_missing_mr_raises(self):
        wf = MRWorkflow()
        with self.assertRaises(KeyError):
            wf.list_discussions(999)


if __name__ == "__main__":
    unittest.main()
