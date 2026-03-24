"""Tests for IssueToPRPipeline (T507)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.pipelines.issue_to_pr import IssueToPRPipeline, PipelineConfig, PipelineResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class FakeIssue:
    number: int
    title: str = "Fix something"
    body: str = "Please fix this"
    url: str = "https://github.com/example/repo/issues/1"
    labels: list = field(default_factory=list)


@dataclass
class FakeFixProposal:
    patch: str = "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new"
    changed_files: list = field(default_factory=list)


def _make_config(**kwargs) -> PipelineConfig:
    defaults = dict(
        project_dir=Path("/tmp/fake_project"),
        max_retries=2,
        require_security_gate=True,
    )
    defaults.update(kwargs)
    return PipelineConfig(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPipelineConfigDefaults:
    def test_config_defaults(self):
        cfg = PipelineConfig(project_dir=Path("/tmp"))
        assert cfg.assignee == "@me"
        assert cfg.label == "lidco"
        assert cfg.auto_merge is False
        assert cfg.require_security_gate is True
        assert cfg.max_retries == 2


class TestRunStepBranchNameFormat:
    def test_branch_name_format(self):
        issue = FakeIssue(number=42)
        cfg = _make_config()
        pipeline = IssueToPRPipeline(cfg)
        with patch("lidco.integrations.issue_trigger.IssueTrigger") as _mock:
            branch = pipeline.run_step_branch(issue)
        assert branch == "lidco/issue-42"


class TestRunStepFixCallsFixFn:
    def test_fix_fn_called_with_issue(self):
        issue = FakeIssue(number=1)
        fix_fn = MagicMock(return_value=FakeFixProposal())
        cfg = _make_config()
        pipeline = IssueToPRPipeline(cfg, fix_fn=fix_fn)
        result = pipeline.run_step_fix(issue, "some-branch")
        fix_fn.assert_called_once_with(issue)
        assert result is not None

    def test_fix_fn_returns_none_propagated(self):
        issue = FakeIssue(number=2)
        pipeline = IssueToPRPipeline(_make_config(), fix_fn=lambda i: None)
        result = pipeline.run_step_fix(issue, "branch")
        assert result is None


class TestRunStepSecurityDelegatesToGate:
    def test_security_step_delegates(self):
        from lidco.review.security_gate import GateResult
        cfg = _make_config()
        pipeline = IssueToPRPipeline(cfg)
        mock_result = GateResult(passed=True, findings=[])
        with patch("lidco.review.security_gate.SecurityGate.check", return_value=mock_result):
            result = pipeline.run_step_security([])
        assert result.passed is True


class TestRunStepReviewEmptyDiff:
    def test_empty_diff_returns_true(self):
        pipeline = IssueToPRPipeline(_make_config())
        assert pipeline.run_step_review("") is True
        assert pipeline.run_step_review("   ") is True


class TestRunStepPRReturnsIntOrNone:
    def test_pr_step_returns_int(self):
        issue = FakeIssue(number=10)
        pipeline = IssueToPRPipeline(_make_config())
        with patch("lidco.review.gh_poster.GHPoster.post_review"):
            result = pipeline.run_step_pr(issue, "lidco/issue-10")
        assert result is None or isinstance(result, int)

    def test_pr_step_returns_deterministic(self):
        issue = FakeIssue(number=99)
        pipeline = IssueToPRPipeline(_make_config())
        with patch("lidco.review.gh_poster.GHPoster.post_review"):
            r1 = pipeline.run_step_pr(issue, "branch")
            r2 = pipeline.run_step_pr(issue, "branch")
        assert r1 == r2


class TestFullRunSuccess:
    def test_full_run_success(self):
        issue = FakeIssue(number=7)
        fix_proposal = FakeFixProposal(patch="diff", changed_files=[])
        fix_fn = MagicMock(return_value=fix_proposal)
        cfg = _make_config()
        pipeline = IssueToPRPipeline(cfg, fix_fn=fix_fn)

        from lidco.review.security_gate import GateResult
        with (
            patch("lidco.integrations.issue_trigger.IssueTrigger"),
            patch("lidco.review.security_gate.SecurityGate.check", return_value=GateResult(passed=True, findings=[])),
            patch("lidco.review.gh_poster.GHPoster.post_review"),
        ):
            result = pipeline.run(issue)

        assert result.status == "success"
        assert result.issue_number == 7
        assert result.security_passed is True
        assert result.error is None


class TestRunBlockedBySecurity:
    def test_run_blocked_by_security(self):
        issue = FakeIssue(number=8)
        fix_proposal = FakeFixProposal()
        cfg = _make_config(require_security_gate=True)
        pipeline = IssueToPRPipeline(cfg, fix_fn=lambda i: fix_proposal)

        from lidco.review.security_gate import GateResult, SecurityFinding
        blocked_result = GateResult(
            passed=False,
            findings=[SecurityFinding(file="f.py", line=1, severity="critical", description="secret")],
            blocked_reason="critical security issue",
        )
        with (
            patch("lidco.integrations.issue_trigger.IssueTrigger"),
            patch("lidco.review.security_gate.SecurityGate.check", return_value=blocked_result),
        ):
            result = pipeline.run(issue)

        assert result.status == "blocked"
        assert result.security_passed is False


class TestRunFixFails:
    def test_run_fix_fails_returns_failed(self):
        issue = FakeIssue(number=9)
        cfg = _make_config(max_retries=0)
        pipeline = IssueToPRPipeline(cfg, fix_fn=lambda i: None)

        with patch("lidco.integrations.issue_trigger.IssueTrigger"):
            result = pipeline.run(issue)

        assert result.status == "failed"
        assert result.pr_number is None


class TestMaxRetriesRespected:
    def test_max_retries_calls_fix_fn_correct_times(self):
        issue = FakeIssue(number=11)
        call_count = [0]

        def counting_fix(i):
            call_count[0] += 1
            return None

        cfg = _make_config(max_retries=2)
        pipeline = IssueToPRPipeline(cfg, fix_fn=counting_fix)

        with patch("lidco.integrations.issue_trigger.IssueTrigger"):
            result = pipeline.run(issue)

        assert result.status == "failed"
        # max_retries=2 means range(0, 3) = 3 attempts
        assert call_count[0] == 3


class TestStepsCompletedTracksEachStep:
    def test_steps_completed_on_success(self):
        issue = FakeIssue(number=12)
        fix_proposal = FakeFixProposal()
        cfg = _make_config()
        pipeline = IssueToPRPipeline(cfg, fix_fn=lambda i: fix_proposal)

        from lidco.review.security_gate import GateResult
        with (
            patch("lidco.integrations.issue_trigger.IssueTrigger"),
            patch("lidco.review.security_gate.SecurityGate.check", return_value=GateResult(passed=True, findings=[])),
            patch("lidco.review.gh_poster.GHPoster.post_review"),
        ):
            result = pipeline.run(issue)

        assert "branch" in result.steps_completed
        assert "fix" in result.steps_completed
        assert "security" in result.steps_completed
        assert "review" in result.steps_completed
        assert "pr" in result.steps_completed


class TestPollAndRunReturnsList:
    def test_poll_and_run_returns_list(self):
        cfg = _make_config()
        pipeline = IssueToPRPipeline(cfg, fix_fn=lambda i: None)

        with patch("lidco.integrations.issue_trigger.IssueTrigger") as mock_cls:
            instance = mock_cls.return_value
            instance.poll.return_value = []
            results = pipeline.poll_and_run()

        assert isinstance(results, list)
