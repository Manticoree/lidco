"""Tests for PR reviewer — Task 453."""

from __future__ import annotations

import asyncio
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lidco.review.pr_reviewer import PRReviewer, ReviewComment, ReviewResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DIFF = """\
diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -10,6 +10,9 @@ def main():
     config = load_config()
+    password = "super_secret_password123"
+    print("debug output")
+    # TODO: fix this later
@@ -20,3 +23,5 @@ def query():
+    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
"""

CLEAN_DIFF = """\
diff --git a/src/utils.py b/src/utils.py
--- a/src/utils.py
+++ b/src/utils.py
@@ -1,3 +1,5 @@
+import logging
+logger = logging.getLogger(__name__)
"""


class TestReviewComment:
    def test_defaults(self) -> None:
        c = ReviewComment(path="a.py", line=1, body="msg")
        assert c.severity == "info"
        assert c.path == "a.py"
        assert c.line == 1
        assert c.body == "msg"


class TestReviewResult:
    def test_has_critical_true(self) -> None:
        r = ReviewResult(pr_number=1, severity_counts={"critical": 2, "info": 1})
        assert r.has_critical() is True

    def test_has_critical_false(self) -> None:
        r = ReviewResult(pr_number=1, severity_counts={"info": 3})
        assert r.has_critical() is False

    def test_total_issues(self) -> None:
        r = ReviewResult(pr_number=1, severity_counts={"critical": 1, "high": 2, "info": 3})
        assert r.total_issues() == 6

    def test_total_issues_empty(self) -> None:
        r = ReviewResult(pr_number=1)
        assert r.total_issues() == 0


class TestFetchDiff:
    @patch("lidco.review.pr_reviewer.subprocess.run")
    def test_fetch_diff_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=SAMPLE_DIFF, stderr=""
        )
        reviewer = PRReviewer()
        diff = reviewer.fetch_diff(42)
        assert diff == SAMPLE_DIFF
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["gh", "pr", "diff", "42"]

    @patch("lidco.review.pr_reviewer.subprocess.run")
    def test_fetch_diff_with_repo(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="diff", stderr="")
        reviewer = PRReviewer()
        diff = reviewer.fetch_diff(10, repo="owner/repo")
        cmd = mock_run.call_args[0][0]
        assert "--repo" in cmd
        assert "owner/repo" in cmd

    @patch("lidco.review.pr_reviewer.subprocess.run")
    def test_fetch_diff_gh_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
        reviewer = PRReviewer()
        result = reviewer.fetch_diff(999)
        assert result is None

    @patch("lidco.review.pr_reviewer.subprocess.run", side_effect=FileNotFoundError("gh not found"))
    def test_fetch_diff_no_gh(self, mock_run: MagicMock) -> None:
        reviewer = PRReviewer()
        result = reviewer.fetch_diff(1)
        assert result is None

    @patch("lidco.review.pr_reviewer.subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 30))
    def test_fetch_diff_timeout(self, mock_run: MagicMock) -> None:
        reviewer = PRReviewer()
        result = reviewer.fetch_diff(1)
        assert result is None


class TestFetchPrInfo:
    @patch("lidco.review.pr_reviewer.subprocess.run")
    def test_fetch_pr_info_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"title":"Fix bug","body":"desc","baseRefName":"main","headRefName":"fix","author":{"login":"dev"}}',
        )
        reviewer = PRReviewer()
        info = reviewer.fetch_pr_info(5)
        assert info["title"] == "Fix bug"

    @patch("lidco.review.pr_reviewer.subprocess.run")
    def test_fetch_pr_info_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="err")
        reviewer = PRReviewer()
        info = reviewer.fetch_pr_info(5)
        assert info == {}


class TestAnalyzeDiff:
    def test_finds_hardcoded_secret(self) -> None:
        reviewer = PRReviewer()
        comments = reviewer.analyze_diff(SAMPLE_DIFF)
        secret_comments = [c for c in comments if c.severity == "critical"]
        assert len(secret_comments) >= 1
        assert any("secret" in c.body.lower() or "key" in c.body.lower() for c in secret_comments)

    def test_finds_todo(self) -> None:
        reviewer = PRReviewer()
        comments = reviewer.analyze_diff(SAMPLE_DIFF)
        todo_comments = [c for c in comments if "TODO" in c.body or "FIXME" in c.body]
        assert len(todo_comments) >= 1

    def test_finds_debug_print(self) -> None:
        reviewer = PRReviewer()
        comments = reviewer.analyze_diff(SAMPLE_DIFF)
        print_comments = [c for c in comments if "print" in c.body.lower() or "console" in c.body.lower()]
        assert len(print_comments) >= 1

    def test_ignores_print_in_test_files(self) -> None:
        test_diff = """\
diff --git a/tests/test_app.py b/tests/test_app.py
--- a/tests/test_app.py
+++ b/tests/test_app.py
@@ -1,3 +1,5 @@
+    print("test debug")
"""
        reviewer = PRReviewer()
        comments = reviewer.analyze_diff(test_diff)
        print_comments = [c for c in comments if "print" in c.body.lower() or "console" in c.body.lower()]
        assert len(print_comments) == 0

    def test_finds_sql_injection(self) -> None:
        reviewer = PRReviewer()
        comments = reviewer.analyze_diff(SAMPLE_DIFF)
        sql_comments = [c for c in comments if "sql" in c.body.lower() or "SQL" in c.body]
        assert len(sql_comments) >= 1

    def test_empty_diff_returns_empty(self) -> None:
        reviewer = PRReviewer()
        assert reviewer.analyze_diff("") == []

    def test_clean_diff_returns_empty(self) -> None:
        reviewer = PRReviewer()
        comments = reviewer.analyze_diff(CLEAN_DIFF)
        assert len(comments) == 0


class TestBuildSummary:
    def test_no_issues(self) -> None:
        reviewer = PRReviewer()
        summary, counts = reviewer.build_summary([])
        assert "No issues" in summary
        assert counts == {}

    def test_counts_severities(self) -> None:
        reviewer = PRReviewer()
        comments = [
            ReviewComment(path="a.py", line=1, body="x", severity="critical"),
            ReviewComment(path="a.py", line=2, body="y", severity="critical"),
            ReviewComment(path="b.py", line=3, body="z", severity="info"),
        ]
        summary, counts = reviewer.build_summary(comments)
        assert counts["critical"] == 2
        assert counts["info"] == 1
        assert "3 issue(s)" in summary


class TestPostComments:
    @patch("lidco.review.pr_reviewer.subprocess.run")
    def test_posts_only_critical_and_high(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        reviewer = PRReviewer()
        comments = [
            ReviewComment(path="a.py", line=1, body="bad", severity="critical"),
            ReviewComment(path="a.py", line=2, body="meh", severity="info"),
            ReviewComment(path="a.py", line=3, body="warn", severity="high"),
        ]
        posted = reviewer.post_comments(42, comments)
        assert posted == 2  # only critical + high
        assert mock_run.call_count == 2

    @patch("lidco.review.pr_reviewer.subprocess.run", side_effect=Exception("network"))
    def test_post_failure_does_not_raise(self, mock_run: MagicMock) -> None:
        reviewer = PRReviewer()
        comments = [ReviewComment(path="a.py", line=1, body="bad", severity="critical")]
        posted = reviewer.post_comments(42, comments)
        assert posted == 0


class TestReviewPipeline:
    @patch.object(PRReviewer, "fetch_diff", return_value=SAMPLE_DIFF)
    def test_review_full_pipeline(self, mock_fetch: MagicMock) -> None:
        reviewer = PRReviewer()
        result = reviewer.review(42)
        assert result.pr_number == 42
        assert result.error is None
        assert len(result.comments) > 0
        assert result.summary != ""
        assert result.total_issues() > 0

    @patch.object(PRReviewer, "fetch_diff", return_value=None)
    def test_review_returns_error_when_diff_fails(self, mock_fetch: MagicMock) -> None:
        reviewer = PRReviewer()
        result = reviewer.review(99)
        assert result.error is not None
        assert "99" in result.error

    @patch.object(PRReviewer, "fetch_diff", return_value=SAMPLE_DIFF)
    @patch.object(PRReviewer, "post_comments", return_value=2)
    def test_review_posts_comments_when_enabled(
        self, mock_post: MagicMock, mock_fetch: MagicMock
    ) -> None:
        reviewer = PRReviewer(post_comments=True)
        result = reviewer.review(42)
        mock_post.assert_called_once()
        assert result.error is None

    @patch.object(PRReviewer, "fetch_diff")
    def test_review_truncates_large_diffs(self, mock_fetch: MagicMock) -> None:
        huge_diff = "+++ b/big.py\n@@ -0,0 +1,5000 @@\n" + "\n".join(
            f"+line{i}" for i in range(5000)
        )
        mock_fetch.return_value = huge_diff
        reviewer = PRReviewer(max_diff_lines=100)
        result = reviewer.review(1)
        # Should not crash, comments based on truncated diff
        assert result.error is None

    @patch.object(PRReviewer, "fetch_diff", return_value=CLEAN_DIFF)
    def test_review_clean_diff_no_issues(self, mock_fetch: MagicMock) -> None:
        reviewer = PRReviewer()
        result = reviewer.review(10)
        assert result.total_issues() == 0
        assert "No issues" in result.summary

    def test_review_result_sorted_by_severity(self) -> None:
        """Verify comments in ReviewResult are sorted critical-first."""
        reviewer = PRReviewer()
        with patch.object(reviewer, "fetch_diff", return_value=SAMPLE_DIFF):
            result = reviewer.review(1)
        if len(result.comments) >= 2:
            from lidco.review.pr_reviewer import SEVERITY_ORDER
            for i in range(len(result.comments) - 1):
                a = SEVERITY_ORDER.get(result.comments[i].severity, 99)
                b = SEVERITY_ORDER.get(result.comments[i + 1].severity, 99)
                assert a <= b


class TestSlashCommand:
    """Test the /review-pr slash command handler."""

    @patch("lidco.review.pr_reviewer.subprocess.run")
    def test_review_pr_handler_missing_args(self, mock_run: MagicMock) -> None:
        from lidco.cli.commands.git_cmds import register

        # We need to capture the registered handler
        registry = MagicMock()
        register(registry)
        # Find the review-pr registration call
        calls = registry.register.call_args_list
        review_cmd = None
        for call in calls:
            cmd = call[0][0]
            if hasattr(cmd, "name") and cmd.name == "review-pr":
                review_cmd = cmd
                break
        assert review_cmd is not None, "review-pr command not registered"
        result = asyncio.run(review_cmd.handler(arg=""))
        assert "Usage" in result

    @patch("lidco.review.pr_reviewer.subprocess.run")
    def test_review_pr_handler_invalid_number(self, mock_run: MagicMock) -> None:
        from lidco.cli.commands.git_cmds import register

        registry = MagicMock()
        register(registry)
        calls = registry.register.call_args_list
        review_cmd = None
        for call in calls:
            cmd = call[0][0]
            if hasattr(cmd, "name") and cmd.name == "review-pr":
                review_cmd = cmd
                break
        assert review_cmd is not None
        result = asyncio.run(review_cmd.handler(arg="abc"))
        assert "Invalid" in result

    @patch.object(PRReviewer, "fetch_diff", return_value=CLEAN_DIFF)
    def test_review_pr_handler_success(self, mock_fetch: MagicMock) -> None:
        from lidco.cli.commands.git_cmds import register

        registry = MagicMock()
        register(registry)
        calls = registry.register.call_args_list
        review_cmd = None
        for call in calls:
            cmd = call[0][0]
            if hasattr(cmd, "name") and cmd.name == "review-pr":
                review_cmd = cmd
                break
        assert review_cmd is not None
        result = asyncio.run(review_cmd.handler(arg="42"))
        assert "No issues" in result
