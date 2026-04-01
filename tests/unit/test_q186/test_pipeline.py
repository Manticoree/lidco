"""Tests for ReviewPipeline — Task 1042."""

from __future__ import annotations

import unittest
from typing import Sequence

from lidco.review.pipeline import (
    ReviewAgent,
    ReviewIssue,
    ReviewPipeline,
    ReviewReport,
    ReviewSeverity,
)


class _StubAgent(ReviewAgent):
    def __init__(self, agent_name: str, issues: list[ReviewIssue] | None = None) -> None:
        self._name = agent_name
        self._issues = issues or []

    @property
    def name(self) -> str:
        return self._name

    def analyze(self, diff: str, files: Sequence[str]) -> list[ReviewIssue]:
        return list(self._issues)


class _FailingAgent(ReviewAgent):
    @property
    def name(self) -> str:
        return "failing"

    def analyze(self, diff: str, files: Sequence[str]) -> list[ReviewIssue]:
        raise RuntimeError("boom")


class TestReviewSeverity(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(ReviewSeverity.CRITICAL.value, "critical")
        self.assertEqual(ReviewSeverity.IMPORTANT.value, "important")
        self.assertEqual(ReviewSeverity.SUGGESTION.value, "suggestion")

    def test_enum_members(self) -> None:
        self.assertEqual(len(ReviewSeverity), 3)


class TestReviewIssue(unittest.TestCase):
    def test_frozen(self) -> None:
        issue = ReviewIssue(
            severity=ReviewSeverity.CRITICAL,
            category="test",
            file="a.py",
            line=1,
            message="msg",
            agent_name="ag",
        )
        with self.assertRaises(AttributeError):
            issue.message = "changed"  # type: ignore[misc]

    def test_fields(self) -> None:
        issue = ReviewIssue(
            severity=ReviewSeverity.SUGGESTION,
            category="cat",
            file="b.py",
            line=42,
            message="hello",
            agent_name="x",
        )
        self.assertEqual(issue.severity, ReviewSeverity.SUGGESTION)
        self.assertEqual(issue.line, 42)


class TestReviewReport(unittest.TestCase):
    def test_empty(self) -> None:
        report = ReviewReport()
        self.assertEqual(report.critical_count, 0)
        self.assertEqual(report.important_count, 0)
        self.assertEqual(report.suggestion_count, 0)
        self.assertIn("No review issues", report.format())

    def test_counts(self) -> None:
        issues = [
            ReviewIssue(ReviewSeverity.CRITICAL, "a", "f", 1, "m", "ag"),
            ReviewIssue(ReviewSeverity.CRITICAL, "a", "f", 2, "m", "ag"),
            ReviewIssue(ReviewSeverity.IMPORTANT, "a", "f", 3, "m", "ag"),
            ReviewIssue(ReviewSeverity.SUGGESTION, "a", "f", 4, "m", "ag"),
        ]
        report = ReviewReport(agents_run=["ag"], issues=issues)
        self.assertEqual(report.critical_count, 2)
        self.assertEqual(report.important_count, 1)
        self.assertEqual(report.suggestion_count, 1)

    def test_issues_by_severity(self) -> None:
        issues = [
            ReviewIssue(ReviewSeverity.CRITICAL, "a", "f", 1, "m", "ag"),
            ReviewIssue(ReviewSeverity.SUGGESTION, "a", "f", 2, "m", "ag"),
        ]
        report = ReviewReport(issues=issues)
        self.assertEqual(len(report.issues_by_severity(ReviewSeverity.CRITICAL)), 1)

    def test_issues_by_agent(self) -> None:
        issues = [
            ReviewIssue(ReviewSeverity.CRITICAL, "a", "f", 1, "m", "alpha"),
            ReviewIssue(ReviewSeverity.CRITICAL, "a", "f", 2, "m", "beta"),
        ]
        report = ReviewReport(issues=issues)
        self.assertEqual(len(report.issues_by_agent("alpha")), 1)

    def test_format_with_issues(self) -> None:
        issues = [
            ReviewIssue(ReviewSeverity.CRITICAL, "err", "main.py", 10, "bad", "ag"),
        ]
        report = ReviewReport(agents_run=["ag"], issues=issues, duration_ms=42.5)
        text = report.format()
        self.assertIn("CRITICAL", text)
        self.assertIn("main.py:10", text)
        self.assertIn("ag", text)


class TestReviewPipeline(unittest.TestCase):
    def test_empty_pipeline(self) -> None:
        pipeline = ReviewPipeline("diff", ["a.py"])
        report = pipeline.run()
        self.assertEqual(report.issues, [])
        self.assertEqual(report.agents_run, [])

    def test_add_agent_returns_new_instance(self) -> None:
        p1 = ReviewPipeline("diff", ["a.py"])
        p2 = p1.add_agent(_StubAgent("stub"))
        self.assertIsNot(p1, p2)
        self.assertEqual(len(p1.agents), 0)
        self.assertEqual(len(p2.agents), 1)

    def test_builder_chain(self) -> None:
        p = (
            ReviewPipeline("diff", [])
            .add_agent(_StubAgent("a"))
            .add_agent(_StubAgent("b"))
        )
        self.assertEqual(len(p.agents), 2)

    def test_run_collects_issues(self) -> None:
        issue = ReviewIssue(ReviewSeverity.CRITICAL, "cat", "f", 1, "msg", "stub")
        pipeline = ReviewPipeline("diff", []).add_agent(_StubAgent("stub", [issue]))
        report = pipeline.run()
        self.assertEqual(len(report.issues), 1)
        self.assertIn("stub", report.agents_run)

    def test_run_sequential(self) -> None:
        pipeline = ReviewPipeline("diff", []).add_agent(_StubAgent("s"))
        report = pipeline.run_sequential()
        self.assertIn("s", report.agents_run)

    def test_run_parallel(self) -> None:
        pipeline = ReviewPipeline("diff", []).add_agent(_StubAgent("p"))
        report = pipeline.run_parallel()
        self.assertIn("p", report.agents_run)

    def test_run_mode_sequential(self) -> None:
        pipeline = ReviewPipeline("diff", []).add_agent(_StubAgent("s"))
        report = pipeline.run(mode="sequential")
        self.assertIn("s", report.agents_run)

    def test_failing_agent_does_not_crash(self) -> None:
        pipeline = ReviewPipeline("diff", []).add_agent(_FailingAgent())
        report = pipeline.run()
        self.assertIn("failing", report.agents_run)
        self.assertEqual(len(report.issues), 0)

    def test_issues_sorted_by_severity(self) -> None:
        issues = [
            ReviewIssue(ReviewSeverity.SUGGESTION, "a", "f", 1, "m", "s"),
            ReviewIssue(ReviewSeverity.CRITICAL, "a", "f", 2, "m", "s"),
            ReviewIssue(ReviewSeverity.IMPORTANT, "a", "f", 3, "m", "s"),
        ]
        pipeline = ReviewPipeline("diff", []).add_agent(_StubAgent("s", issues))
        report = pipeline.run()
        self.assertEqual(report.issues[0].severity, ReviewSeverity.CRITICAL)
        self.assertEqual(report.issues[1].severity, ReviewSeverity.IMPORTANT)
        self.assertEqual(report.issues[2].severity, ReviewSeverity.SUGGESTION)

    def test_duration_positive(self) -> None:
        pipeline = ReviewPipeline("diff", []).add_agent(_StubAgent("s"))
        report = pipeline.run()
        self.assertGreaterEqual(report.duration_ms, 0)

    def test_properties(self) -> None:
        p = ReviewPipeline("my diff", ["x.py", "y.py"])
        self.assertEqual(p.diff_text, "my diff")
        self.assertEqual(p.changed_files, ("x.py", "y.py"))

    def test_immutable_changed_files(self) -> None:
        files = ["a.py"]
        p = ReviewPipeline("diff", files)
        files.append("b.py")
        self.assertEqual(p.changed_files, ("a.py",))


if __name__ == "__main__":
    unittest.main()
