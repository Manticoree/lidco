"""Tests for review_learn.trainer (Q332, task 1773)."""
from __future__ import annotations

import unittest

from lidco.review_learn.trainer import (
    Difficulty,
    ReviewIssue,
    ReviewSubmission,
    ReviewTrainer,
    SamplePR,
    TrainingScore,
    create_default_trainer,
)


class TestSamplePR(unittest.TestCase):
    def test_issue_count(self) -> None:
        pr = SamplePR(
            pr_id="t1", title="T", description="D", diff="+x",
            language="python", difficulty=Difficulty.BEGINNER,
            issues=(ReviewIssue("a", line=1), ReviewIssue("b", line=2)),
        )
        self.assertEqual(pr.issue_count, 2)

    def test_frozen(self) -> None:
        pr = SamplePR(pr_id="t1", title="T", description="D", diff="+x",
                       language="python", difficulty=Difficulty.BEGINNER)
        with self.assertRaises(AttributeError):
            pr.title = "new"  # type: ignore[misc]


class TestReviewIssue(unittest.TestCase):
    def test_defaults(self) -> None:
        issue = ReviewIssue("desc", line=5)
        self.assertEqual(issue.severity, "warning")
        self.assertEqual(issue.hint, "")


class TestReviewSubmission(unittest.TestCase):
    def test_timestamp(self) -> None:
        sub = ReviewSubmission(pr_id="t1", found_issues=["a"])
        self.assertGreater(sub.submitted_at, 0)


class TestTrainingScore(unittest.TestCase):
    def test_grade_a(self) -> None:
        s = TrainingScore(pr_id="x", issues_found=2, issues_total=2, precision=1.0, recall=1.0, score=95.0, feedback="")
        self.assertEqual(s.grade, "A")

    def test_grade_b(self) -> None:
        s = TrainingScore(pr_id="x", issues_found=1, issues_total=2, precision=0.5, recall=0.5, score=82.0, feedback="")
        self.assertEqual(s.grade, "B")

    def test_grade_c(self) -> None:
        s = TrainingScore(pr_id="x", issues_found=1, issues_total=2, precision=0.5, recall=0.5, score=72.0, feedback="")
        self.assertEqual(s.grade, "C")

    def test_grade_d(self) -> None:
        s = TrainingScore(pr_id="x", issues_found=1, issues_total=3, precision=0.3, recall=0.3, score=65.0, feedback="")
        self.assertEqual(s.grade, "D")

    def test_grade_f(self) -> None:
        s = TrainingScore(pr_id="x", issues_found=0, issues_total=3, precision=0.0, recall=0.0, score=20.0, feedback="")
        self.assertEqual(s.grade, "F")


class TestReviewTrainer(unittest.TestCase):
    def _make_sample(self, pr_id: str = "pr-1", issues: tuple[ReviewIssue, ...] = ()) -> SamplePR:
        return SamplePR(
            pr_id=pr_id, title="Test PR", description="Desc",
            diff="+code", language="python", difficulty=Difficulty.BEGINNER,
            issues=issues,
        )

    def test_add_and_get(self) -> None:
        t = ReviewTrainer()
        s = self._make_sample()
        t.add_sample(s)
        self.assertEqual(t.sample_count, 1)
        self.assertIs(t.get_sample("pr-1"), s)

    def test_remove_sample(self) -> None:
        t = ReviewTrainer()
        t.add_sample(self._make_sample())
        self.assertTrue(t.remove_sample("pr-1"))
        self.assertFalse(t.remove_sample("pr-1"))
        self.assertEqual(t.sample_count, 0)

    def test_list_samples_by_difficulty(self) -> None:
        t = ReviewTrainer()
        t.add_sample(self._make_sample("a"))
        t.add_sample(SamplePR(
            pr_id="b", title="B", description="D", diff="+x",
            language="python", difficulty=Difficulty.ADVANCED,
        ))
        beginners = t.list_samples(Difficulty.BEGINNER)
        self.assertEqual(len(beginners), 1)
        self.assertEqual(beginners[0].pr_id, "a")

    def test_submit_perfect_review(self) -> None:
        t = ReviewTrainer()
        t.add_sample(self._make_sample(issues=(
            ReviewIssue("bug a", line=1),
            ReviewIssue("bug b", line=2),
        )))
        sub = ReviewSubmission(pr_id="pr-1", found_issues=["bug a", "bug b"])
        score = t.submit_review(sub)
        self.assertEqual(score.issues_found, 2)
        self.assertEqual(score.issues_total, 2)
        self.assertEqual(score.recall, 1.0)
        self.assertIn("Perfect review", score.feedback)

    def test_submit_partial_review(self) -> None:
        t = ReviewTrainer()
        t.add_sample(self._make_sample(issues=(
            ReviewIssue("bug a", line=1),
            ReviewIssue("bug b", line=2),
        )))
        sub = ReviewSubmission(pr_id="pr-1", found_issues=["bug a"])
        score = t.submit_review(sub)
        self.assertEqual(score.issues_found, 1)
        self.assertEqual(score.recall, 0.5)
        self.assertIn("Missed issues", score.feedback)

    def test_submit_false_positives(self) -> None:
        t = ReviewTrainer()
        t.add_sample(self._make_sample(issues=(ReviewIssue("bug a", line=1),)))
        sub = ReviewSubmission(pr_id="pr-1", found_issues=["bug a", "not real"])
        score = t.submit_review(sub)
        self.assertIn("False positives", score.feedback)

    def test_submit_unknown_pr(self) -> None:
        t = ReviewTrainer()
        sub = ReviewSubmission(pr_id="unknown", found_issues=[])
        with self.assertRaises(ValueError):
            t.submit_review(sub)

    def test_get_scores(self) -> None:
        t = ReviewTrainer()
        t.add_sample(self._make_sample(issues=(ReviewIssue("a", line=1),)))
        t.submit_review(ReviewSubmission(pr_id="pr-1", found_issues=["a"]))
        scores = t.get_scores()
        self.assertEqual(len(scores), 1)
        scores_filtered = t.get_scores("pr-1")
        self.assertEqual(len(scores_filtered), 1)
        self.assertEqual(t.get_scores("other"), [])

    def test_average_score_empty(self) -> None:
        t = ReviewTrainer()
        self.assertEqual(t.average_score(), 0.0)

    def test_guided_hints(self) -> None:
        t = ReviewTrainer()
        t.add_sample(self._make_sample(issues=(
            ReviewIssue("a", line=1, hint="Check line 1"),
            ReviewIssue("b", line=5),
        )))
        hints = t.guided_hints("pr-1")
        self.assertEqual(len(hints), 2)
        self.assertEqual(hints[0], "Check line 1")
        self.assertIn("line 5", hints[1])

    def test_guided_hints_unknown(self) -> None:
        t = ReviewTrainer()
        self.assertEqual(t.guided_hints("nope"), [])

    def test_no_issues_pr_score(self) -> None:
        t = ReviewTrainer()
        t.add_sample(self._make_sample(issues=()))
        sub = ReviewSubmission(pr_id="pr-1", found_issues=[])
        score = t.submit_review(sub)
        self.assertEqual(score.score, 100.0)


class TestCreateDefaultTrainer(unittest.TestCase):
    def test_has_samples(self) -> None:
        t = create_default_trainer()
        self.assertGreaterEqual(t.sample_count, 2)

    def test_sample_001_exists(self) -> None:
        t = create_default_trainer()
        s = t.get_sample("sample-001")
        self.assertIsNotNone(s)
        self.assertGreater(s.issue_count, 0)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
