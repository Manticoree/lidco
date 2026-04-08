"""Tests for review_learn.analytics (Q332, task 1775)."""
from __future__ import annotations

import unittest

from lidco.review_learn.analytics import (
    ReviewAnalytics,
    ReviewEvent,
    ReviewerStats,
    TrendPoint,
)


class TestReviewEvent(unittest.TestCase):
    def test_adoption_rate(self) -> None:
        e = ReviewEvent(review_id="r1", reviewer="alice", pr_id="pr-1",
                        issues_found=10, issues_adopted=7)
        self.assertAlmostEqual(e.adoption_rate, 0.7)

    def test_adoption_rate_zero_issues(self) -> None:
        e = ReviewEvent(review_id="r1", reviewer="alice", pr_id="pr-1",
                        issues_found=0, issues_adopted=0)
        self.assertEqual(e.adoption_rate, 0.0)

    def test_timestamp_auto(self) -> None:
        e = ReviewEvent(review_id="r1", reviewer="alice", pr_id="pr-1")
        self.assertGreater(e.timestamp, 0)

    def test_frozen(self) -> None:
        e = ReviewEvent(review_id="r1", reviewer="alice", pr_id="pr-1")
        with self.assertRaises(AttributeError):
            e.reviewer = "bob"  # type: ignore[misc]


class TestReviewAnalytics(unittest.TestCase):
    def _event(self, reviewer: str = "alice", issues: int = 5,
               adopted: int = 3, time_s: float = 120.0,
               ts: float = 0.0, **kw) -> ReviewEvent:
        return ReviewEvent(
            review_id=kw.get("review_id", "r1"),
            reviewer=reviewer, pr_id=kw.get("pr_id", "pr-1"),
            issues_found=issues, issues_adopted=adopted,
            review_time_seconds=time_s, timestamp=ts,
        )

    def test_record_and_count(self) -> None:
        a = ReviewAnalytics()
        a.record_event(self._event())
        self.assertEqual(a.event_count, 1)

    def test_reviewer_stats(self) -> None:
        a = ReviewAnalytics()
        a.record_event(self._event(reviewer="alice", issues=4, adopted=2, time_s=100))
        a.record_event(self._event(reviewer="alice", issues=6, adopted=4, time_s=200, review_id="r2"))
        stats = a.reviewer_stats("alice")
        self.assertIsNotNone(stats)
        self.assertEqual(stats.total_reviews, 2)  # type: ignore[union-attr]
        self.assertEqual(stats.total_issues, 10)  # type: ignore[union-attr]
        self.assertEqual(stats.total_adopted, 6)  # type: ignore[union-attr]
        self.assertEqual(stats.avg_review_time, 150.0)  # type: ignore[union-attr]
        self.assertAlmostEqual(stats.adoption_rate, 0.6)  # type: ignore[union-attr]

    def test_reviewer_stats_unknown(self) -> None:
        a = ReviewAnalytics()
        self.assertIsNone(a.reviewer_stats("bob"))

    def test_list_reviewers(self) -> None:
        a = ReviewAnalytics()
        a.record_event(self._event(reviewer="bob"))
        a.record_event(self._event(reviewer="alice", review_id="r2"))
        self.assertEqual(a.list_reviewers(), ["alice", "bob"])

    def test_record_issue_and_common_issues(self) -> None:
        a = ReviewAnalytics()
        a.record_issue("naming", adopted=True)
        a.record_issue("naming", adopted=False)
        a.record_issue("security", adopted=True)
        issues = a.common_issues()
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0].issue_type, "naming")
        self.assertEqual(issues[0].count, 2)
        self.assertAlmostEqual(issues[0].adoption_rate, 0.5)

    def test_common_issues_top_n(self) -> None:
        a = ReviewAnalytics()
        for i in range(20):
            a.record_issue(f"type-{i}")
        top5 = a.common_issues(top_n=5)
        self.assertEqual(len(top5), 5)

    def test_adoption_rate_overall(self) -> None:
        a = ReviewAnalytics()
        a.record_event(self._event(issues=10, adopted=5))
        a.record_event(self._event(issues=10, adopted=8, review_id="r2"))
        self.assertAlmostEqual(a.adoption_rate(), 0.65)

    def test_adoption_rate_empty(self) -> None:
        a = ReviewAnalytics()
        self.assertEqual(a.adoption_rate(), 0.0)

    def test_average_review_time(self) -> None:
        a = ReviewAnalytics()
        a.record_event(self._event(time_s=100))
        a.record_event(self._event(time_s=200, review_id="r2"))
        self.assertEqual(a.average_review_time(), 150.0)

    def test_average_review_time_empty(self) -> None:
        a = ReviewAnalytics()
        self.assertEqual(a.average_review_time(), 0.0)

    def test_improvement_trend(self) -> None:
        a = ReviewAnalytics()
        for i in range(10):
            a.record_event(self._event(
                reviewer="alice", issues=10, adopted=i,
                time_s=60, ts=float(i * 100), review_id=f"r{i}",
            ))
        trend = a.improvement_trend(reviewer="alice", periods=5)
        self.assertGreaterEqual(len(trend), 1)
        self.assertLessEqual(len(trend), 5)
        self.assertTrue(all(isinstance(t, TrendPoint) for t in trend))

    def test_improvement_trend_empty(self) -> None:
        a = ReviewAnalytics()
        self.assertEqual(a.improvement_trend(), [])

    def test_summary(self) -> None:
        a = ReviewAnalytics()
        a.record_event(self._event())
        s = a.summary()
        self.assertEqual(s["total_reviews"], 1)
        self.assertEqual(s["unique_reviewers"], 1)
        self.assertIn("adoption_rate", s)
        self.assertIn("avg_review_time", s)

    def test_reviewer_stats_zero_issues(self) -> None:
        a = ReviewAnalytics()
        a.record_event(self._event(reviewer="bob", issues=0, adopted=0))
        stats = a.reviewer_stats("bob")
        self.assertEqual(stats.adoption_rate, 0.0)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
