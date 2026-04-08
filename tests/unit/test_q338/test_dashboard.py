"""Tests for CommunityDashboard (Task 1805)."""
from __future__ import annotations

import unittest

from lidco.community.dashboard import (
    ActivityEntry,
    CommunityDashboard,
    CommunityStats,
    ContributorStats,
)


class TestActivityEntry(unittest.TestCase):
    def test_defaults(self):
        e = ActivityEntry(actor="alice", action="published", target="linter")
        self.assertEqual(e.actor, "alice")
        self.assertGreater(e.timestamp, 0)

    def test_to_dict(self):
        e = ActivityEntry(actor="alice", action="published", target="linter")
        d = e.to_dict()
        self.assertEqual(d["actor"], "alice")
        self.assertEqual(d["action"], "published")


class TestContributorStats(unittest.TestCase):
    def test_score(self):
        cs = ContributorStats(name="alice", plugins=2, themes=1, recipes=1, reviews=5)
        # 2*10 + 1*5 + 1*5 + 5*1 = 35
        self.assertEqual(cs.score, 35)

    def test_score_zero(self):
        cs = ContributorStats(name="bob")
        self.assertEqual(cs.score, 0)

    def test_to_dict(self):
        cs = ContributorStats(name="alice", plugins=1)
        d = cs.to_dict()
        self.assertEqual(d["name"], "alice")
        self.assertIn("score", d)


class TestCommunityStats(unittest.TestCase):
    def test_defaults(self):
        s = CommunityStats()
        self.assertEqual(s.total_plugins, 0)
        self.assertEqual(s.total_downloads, 0)

    def test_to_dict(self):
        s = CommunityStats(total_plugins=5)
        d = s.to_dict()
        self.assertEqual(d["total_plugins"], 5)


class TestCommunityDashboard(unittest.TestCase):
    def setUp(self):
        self.dash = CommunityDashboard()

    def test_empty(self):
        self.assertEqual(self.dash.activity_count, 0)
        st = self.dash.get_stats()
        self.assertEqual(st.total_plugins, 0)

    def test_record_plugin(self):
        self.dash.record_plugin("alice", "linter")
        st = self.dash.get_stats()
        self.assertEqual(st.total_plugins, 1)
        self.assertEqual(st.total_contributors, 1)

    def test_record_theme(self):
        self.dash.record_theme("alice", "dark-mode")
        st = self.dash.get_stats()
        self.assertEqual(st.total_themes, 1)

    def test_record_recipe(self):
        self.dash.record_recipe("bob", "auto-lint")
        st = self.dash.get_stats()
        self.assertEqual(st.total_recipes, 1)

    def test_record_review(self):
        self.dash.record_review("bob", "linter")
        st = self.dash.get_stats()
        self.assertEqual(st.total_reviews, 1)

    def test_record_download(self):
        self.dash.record_download()
        st = self.dash.get_stats()
        self.assertEqual(st.total_downloads, 1)

    def test_recent_activity(self):
        self.dash.record_plugin("alice", "p1")
        self.dash.record_theme("bob", "t1")
        activity = self.dash.recent_activity()
        self.assertEqual(len(activity), 2)
        # Most recent first
        self.assertEqual(activity[0].target, "t1")

    def test_recent_activity_limit(self):
        for i in range(30):
            self.dash.record_plugin(f"user{i}", f"p{i}")
        activity = self.dash.recent_activity(limit=5)
        self.assertEqual(len(activity), 5)

    def test_leaderboard(self):
        self.dash.record_plugin("alice", "p1")
        self.dash.record_plugin("alice", "p2")
        self.dash.record_theme("bob", "t1")
        leaders = self.dash.leaderboard()
        self.assertEqual(leaders[0].name, "alice")  # 20 > 5

    def test_leaderboard_limit(self):
        for i in range(20):
            self.dash.record_plugin(f"user{i}", f"p{i}")
        leaders = self.dash.leaderboard(limit=5)
        self.assertEqual(len(leaders), 5)

    def test_get_contributor(self):
        self.dash.record_plugin("alice", "linter")
        cs = self.dash.get_contributor("alice")
        self.assertIsNotNone(cs)
        self.assertEqual(cs.plugins, 1)

    def test_get_contributor_not_found(self):
        self.assertIsNone(self.dash.get_contributor("nobody"))

    def test_popular_plugins(self):
        plugins = [
            {"name": "a", "downloads": 100},
            {"name": "b", "downloads": 500},
            {"name": "c", "downloads": 50},
        ]
        top = self.dash.popular_plugins(plugins, limit=2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0]["name"], "b")

    def test_record_activity_creates_contributor(self):
        entry = ActivityEntry(actor="charlie", action="installed", target="x")
        self.dash.record_activity(entry)
        cs = self.dash.get_contributor("charlie")
        self.assertIsNotNone(cs)

    def test_multiple_contributions(self):
        self.dash.record_plugin("alice", "p1")
        self.dash.record_theme("alice", "t1")
        self.dash.record_recipe("alice", "r1")
        self.dash.record_review("alice", "x")
        cs = self.dash.get_contributor("alice")
        self.assertEqual(cs.plugins, 1)
        self.assertEqual(cs.themes, 1)
        self.assertEqual(cs.recipes, 1)
        self.assertEqual(cs.reviews, 1)
        self.assertEqual(cs.score, 10 + 5 + 5 + 1)


if __name__ == "__main__":
    unittest.main()
