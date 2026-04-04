"""Tests for lidco.branches.dashboard."""
from __future__ import annotations

import time
import unittest

from lidco.branches.dashboard import BranchDashboard2


class TestAddBranch(unittest.TestCase):
    def test_add_single(self):
        d = BranchDashboard2()
        d.add_branch("feature/x", ahead=2, behind=1, author="alice")
        self.assertEqual(len(d._branches), 1)

    def test_add_multiple(self):
        d = BranchDashboard2()
        d.add_branch("feature/a", author="alice")
        d.add_branch("feature/b", author="bob")
        self.assertEqual(len(d._branches), 2)

    def test_defaults(self):
        d = BranchDashboard2()
        d.add_branch("feature/x")
        b = d._branches[0]
        self.assertEqual(b.ahead, 0)
        self.assertEqual(b.behind, 0)
        self.assertEqual(b.author, "")
        self.assertEqual(b.last_activity, 0.0)


class TestOverview(unittest.TestCase):
    def test_empty(self):
        d = BranchDashboard2()
        self.assertEqual(d.overview(), [])

    def test_overview_fields(self):
        d = BranchDashboard2()
        d.add_branch("feature/x", ahead=3, behind=1, author="alice", last_activity=100.0)
        ov = d.overview()
        self.assertEqual(len(ov), 1)
        self.assertEqual(ov[0]["name"], "feature/x")
        self.assertEqual(ov[0]["ahead"], 3)
        self.assertEqual(ov[0]["behind"], 1)
        self.assertEqual(ov[0]["author"], "alice")
        self.assertEqual(ov[0]["last_activity"], 100.0)

    def test_overview_multiple(self):
        d = BranchDashboard2()
        d.add_branch("a")
        d.add_branch("b")
        d.add_branch("c")
        self.assertEqual(len(d.overview()), 3)


class TestActiveAuthors(unittest.TestCase):
    def test_empty(self):
        d = BranchDashboard2()
        self.assertEqual(d.active_authors(), [])

    def test_deduplicates(self):
        d = BranchDashboard2()
        d.add_branch("a", author="alice")
        d.add_branch("b", author="alice")
        d.add_branch("c", author="bob")
        self.assertEqual(d.active_authors(), ["alice", "bob"])

    def test_skips_empty_author(self):
        d = BranchDashboard2()
        d.add_branch("a", author="")
        d.add_branch("b", author="charlie")
        self.assertEqual(d.active_authors(), ["charlie"])

    def test_sorted(self):
        d = BranchDashboard2()
        d.add_branch("a", author="zara")
        d.add_branch("b", author="alice")
        self.assertEqual(d.active_authors(), ["alice", "zara"])


class TestMergeStatus(unittest.TestCase):
    def test_empty(self):
        d = BranchDashboard2()
        ms = d.merge_status()
        self.assertEqual(ms["ahead_only"], 0)
        self.assertEqual(ms["behind_only"], 0)
        self.assertEqual(ms["diverged"], 0)
        self.assertEqual(ms["up_to_date"], 0)

    def test_ahead_only(self):
        d = BranchDashboard2()
        d.add_branch("a", ahead=5, behind=0)
        self.assertEqual(d.merge_status()["ahead_only"], 1)

    def test_behind_only(self):
        d = BranchDashboard2()
        d.add_branch("a", ahead=0, behind=3)
        self.assertEqual(d.merge_status()["behind_only"], 1)

    def test_diverged(self):
        d = BranchDashboard2()
        d.add_branch("a", ahead=2, behind=4)
        self.assertEqual(d.merge_status()["diverged"], 1)

    def test_up_to_date(self):
        d = BranchDashboard2()
        d.add_branch("a", ahead=0, behind=0)
        self.assertEqual(d.merge_status()["up_to_date"], 1)

    def test_mixed(self):
        d = BranchDashboard2()
        d.add_branch("a", ahead=1, behind=0)
        d.add_branch("b", ahead=0, behind=1)
        d.add_branch("c", ahead=1, behind=1)
        d.add_branch("d", ahead=0, behind=0)
        ms = d.merge_status()
        self.assertEqual(ms["ahead_only"], 1)
        self.assertEqual(ms["behind_only"], 1)
        self.assertEqual(ms["diverged"], 1)
        self.assertEqual(ms["up_to_date"], 1)


class TestSummary(unittest.TestCase):
    def test_empty(self):
        d = BranchDashboard2()
        s = d.summary()
        self.assertEqual(s["total"], 0)
        self.assertEqual(s["authors"], 0)

    def test_with_data(self):
        d = BranchDashboard2()
        d.add_branch("a", author="alice", ahead=1)
        d.add_branch("b", author="bob", ahead=0, behind=1)
        s = d.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["authors"], 2)
        self.assertIn("ahead_only", s["merge_status"])


if __name__ == "__main__":
    unittest.main()
