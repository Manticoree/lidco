"""Tests for BugBotPRPoster (Task 699)."""
import unittest
from unittest.mock import MagicMock

from lidco.review.bugbot_pr_trigger import BugBotFinding, BugSeverity
from lidco.review.bugbot_fix_agent import BugBotFixProposal
from lidco.review.bugbot_pr_poster import BugBotPRPoster, PostResult


def _finding(rule_id: str = "bare_except", severity: BugSeverity = BugSeverity.MEDIUM,
             file: str = "test.py", line: int = 5) -> BugBotFinding:
    return BugBotFinding(file=file, line=line, severity=severity, message="msg", rule_id=rule_id)


def _proposal(rule_id: str = "bare_except", severity: BugSeverity = BugSeverity.MEDIUM,
              file: str = "test.py", line: int = 5, patch: str = "diff",
              confidence: float = 0.8) -> BugBotFixProposal:
    return BugBotFixProposal(
        finding=_finding(rule_id, severity, file, line),
        patch=patch,
        rationale="reason",
        confidence=confidence,
    )


class TestPostResult(unittest.TestCase):
    def test_creation(self):
        r = PostResult(posted=2, skipped=1, errors=[], comment_ids=["a", "b"])
        self.assertEqual(r.posted, 2)
        self.assertEqual(r.skipped, 1)

    def test_with_errors(self):
        r = PostResult(posted=0, skipped=0, errors=["err1"], comment_ids=[])
        self.assertEqual(len(r.errors), 1)


class TestDryRun(unittest.TestCase):
    def setUp(self):
        self.poster = BugBotPRPoster()

    def test_dry_run_no_gh_poster(self):
        proposals = [_proposal()]
        result = self.poster.post(proposals, pr_number=42, dry_run=True)
        self.assertEqual(result.posted, 1)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(len(result.errors), 0)

    def test_dry_run_comment_ids(self):
        proposals = [_proposal(), _proposal(file="b.py")]
        result = self.poster.post(proposals, pr_number=1, dry_run=True)
        self.assertEqual(len(result.comment_ids), 2)
        self.assertTrue(all("dry-run" in cid for cid in result.comment_ids))

    def test_dry_run_multiple_proposals(self):
        proposals = [_proposal(file=f"f{i}.py") for i in range(5)]
        result = self.poster.post(proposals, pr_number=1, dry_run=True)
        self.assertEqual(result.posted, 5)


class TestSkipLogic(unittest.TestCase):
    def setUp(self):
        self.poster = BugBotPRPoster()

    def test_skip_empty_patch_low_confidence(self):
        p = _proposal(patch="", confidence=0.1)
        result = self.poster.post([p], pr_number=1, dry_run=True)
        self.assertEqual(result.skipped, 1)
        self.assertEqual(result.posted, 0)

    def test_do_not_skip_empty_patch_high_confidence(self):
        p = _proposal(patch="", confidence=0.5)
        result = self.poster.post([p], pr_number=1, dry_run=True)
        self.assertEqual(result.posted, 1)

    def test_do_not_skip_with_patch_low_confidence(self):
        p = _proposal(patch="some fix", confidence=0.1)
        result = self.poster.post([p], pr_number=1, dry_run=True)
        self.assertEqual(result.posted, 1)

    def test_skip_boundary_confidence_0_3(self):
        # confidence < 0.3 means strictly less than
        p = _proposal(patch="", confidence=0.29)
        result = self.poster.post([p], pr_number=1, dry_run=True)
        self.assertEqual(result.skipped, 1)

    def test_empty_patch_exactly_0_3_not_skipped(self):
        p = _proposal(patch="", confidence=0.3)
        result = self.poster.post([p], pr_number=1, dry_run=True)
        self.assertEqual(result.posted, 1)


class TestDuplicateDetection(unittest.TestCase):
    def setUp(self):
        self.poster = BugBotPRPoster()

    def test_duplicate_skipped(self):
        p = _proposal()
        result1 = self.poster.post([p], pr_number=1, dry_run=True)
        result2 = self.poster.post([p], pr_number=1, dry_run=True)
        self.assertEqual(result1.posted, 1)
        self.assertEqual(result2.skipped, 1)
        self.assertEqual(result2.posted, 0)

    def test_clear_posted_resets(self):
        p = _proposal()
        self.poster.post([p], pr_number=1, dry_run=True)
        self.poster.clear_posted()
        result = self.poster.post([p], pr_number=1, dry_run=True)
        self.assertEqual(result.posted, 1)

    def test_different_files_not_duplicate(self):
        p1 = _proposal(file="a.py")
        p2 = _proposal(file="b.py")
        result = self.poster.post([p1, p2], pr_number=1, dry_run=True)
        self.assertEqual(result.posted, 2)

    def test_different_lines_not_duplicate(self):
        p1 = _proposal(line=1)
        p2 = _proposal(line=2)
        result = self.poster.post([p1, p2], pr_number=1, dry_run=True)
        self.assertEqual(result.posted, 2)


class TestSeveritySorting(unittest.TestCase):
    def test_critical_posted_first(self):
        gh = MagicMock()
        posted_order = []
        def mock_post(pr, file, line, body):
            posted_order.append(file)
            return f"id-{file}"
        gh.post_comment = mock_post
        poster = BugBotPRPoster(gh_poster=gh)
        proposals = [
            _proposal(severity=BugSeverity.LOW, file="low.py"),
            _proposal(severity=BugSeverity.CRITICAL, file="crit.py"),
            _proposal(severity=BugSeverity.HIGH, file="high.py"),
        ]
        poster.post(proposals, pr_number=1)
        self.assertEqual(posted_order[0], "crit.py")


class TestFormatComment(unittest.TestCase):
    def setUp(self):
        self.poster = BugBotPRPoster()

    def test_format_includes_severity(self):
        p = _proposal(severity=BugSeverity.CRITICAL)
        body = self.poster.format_comment(p)
        self.assertIn("CRITICAL", body)

    def test_format_includes_rule_id(self):
        p = _proposal(rule_id="eval_usage")
        body = self.poster.format_comment(p)
        self.assertIn("eval_usage", body)

    def test_format_includes_message(self):
        p = _proposal()
        body = self.poster.format_comment(p)
        self.assertIn("msg", body)

    def test_format_includes_patch(self):
        p = _proposal(patch="- old\n+ new")
        body = self.poster.format_comment(p)
        self.assertIn("```diff", body)
        self.assertIn("- old", body)

    def test_format_no_patch_no_diff_block(self):
        p = _proposal(patch="")
        body = self.poster.format_comment(p)
        self.assertNotIn("```diff", body)

    def test_format_includes_confidence(self):
        p = _proposal(confidence=0.9)
        body = self.poster.format_comment(p)
        self.assertIn("90%", body)

    def test_format_includes_rationale(self):
        p = _proposal()
        body = self.poster.format_comment(p)
        self.assertIn("reason", body)


class TestWithGHPoster(unittest.TestCase):
    def test_posts_to_gh_poster(self):
        gh = MagicMock()
        gh.post_comment.return_value = "comment-123"
        poster = BugBotPRPoster(gh_poster=gh)
        result = poster.post([_proposal()], pr_number=42)
        gh.post_comment.assert_called_once()
        self.assertEqual(result.posted, 1)
        self.assertIn("comment-123", result.comment_ids)

    def test_gh_poster_exception(self):
        gh = MagicMock()
        gh.post_comment.side_effect = RuntimeError("API error")
        poster = BugBotPRPoster(gh_poster=gh)
        result = poster.post([_proposal()], pr_number=1)
        self.assertEqual(result.posted, 0)
        self.assertEqual(len(result.errors), 1)

    def test_no_gh_poster_skips(self):
        poster = BugBotPRPoster()
        result = poster.post([_proposal()], pr_number=1, dry_run=False)
        self.assertEqual(result.skipped, 1)


class TestEmptyProposals(unittest.TestCase):
    def test_empty_list(self):
        poster = BugBotPRPoster()
        result = poster.post([], pr_number=1)
        self.assertEqual(result.posted, 0)
        self.assertEqual(result.skipped, 0)


if __name__ == "__main__":
    unittest.main()
