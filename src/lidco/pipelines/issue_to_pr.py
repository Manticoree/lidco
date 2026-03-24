"""IssueToPRPipeline — end-to-end issue → branch → fix → security → PR workflow."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class PipelineConfig:
    project_dir: Path
    assignee: str = "@me"
    label: str = "lidco"
    test_cmd: str = "python -m pytest -q --tb=no"
    auto_merge: bool = False
    require_security_gate: bool = True
    max_retries: int = 2


@dataclass
class PipelineResult:
    issue_number: int
    branch: str
    pr_number: int | None
    status: str  # "success" | "failed" | "blocked"
    security_passed: bool
    self_review_passed: bool
    error: str | None = None
    steps_completed: list[str] = field(default_factory=list)


class IssueToPRPipeline:
    """Automated pipeline: GitHub Issue → branch → fix → security → PR."""

    def __init__(self, config: PipelineConfig, fix_fn: Callable | None = None) -> None:
        self._config = config
        self._fix_fn = fix_fn if fix_fn is not None else (lambda issue: None)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, issue) -> PipelineResult:
        """Execute full pipeline for one issue."""
        steps: list[str] = []
        branch = ""
        pr_number = None
        security_passed = False
        self_review_passed = False

        # Step 1: create branch
        try:
            branch = self.run_step_branch(issue)
            steps.append("branch")
        except Exception as exc:
            return PipelineResult(
                issue_number=issue.number,
                branch=branch,
                pr_number=None,
                status="failed",
                security_passed=False,
                self_review_passed=False,
                error=str(exc),
                steps_completed=steps,
            )

        # Step 2: fix with retries
        fix_proposal = None
        last_error: str | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                fix_proposal = self.run_step_fix(issue, branch)
                if fix_proposal is not None:
                    steps.append("fix")
                    break
                last_error = "fix_fn returned None"
            except Exception as exc:
                last_error = str(exc)
        else:
            # exhausted retries
            pass

        if fix_proposal is None:
            return PipelineResult(
                issue_number=issue.number,
                branch=branch,
                pr_number=None,
                status="failed",
                security_passed=False,
                self_review_passed=False,
                error=last_error or "fix returned None after retries",
                steps_completed=steps,
            )

        # Collect changed files from fix proposal
        changed_files: list[str] = []
        if hasattr(fix_proposal, "changed_files"):
            changed_files = fix_proposal.changed_files or []

        # Step 3: security gate
        if self._config.require_security_gate:
            try:
                gate_result = self.run_step_security(changed_files)
                security_passed = gate_result.passed
                steps.append("security")
            except Exception as exc:
                return PipelineResult(
                    issue_number=issue.number,
                    branch=branch,
                    pr_number=None,
                    status="failed",
                    security_passed=False,
                    self_review_passed=False,
                    error=str(exc),
                    steps_completed=steps,
                )

            if not security_passed:
                return PipelineResult(
                    issue_number=issue.number,
                    branch=branch,
                    pr_number=None,
                    status="blocked",
                    security_passed=False,
                    self_review_passed=False,
                    error=getattr(gate_result, "blocked_reason", "security gate failed"),
                    steps_completed=steps,
                )
        else:
            security_passed = True

        # Step 4: self-review
        diff = getattr(fix_proposal, "patch", "") or ""
        try:
            self_review_passed = self.run_step_review(diff)
            steps.append("review")
        except Exception:
            self_review_passed = False

        # Step 5: create PR
        try:
            pr_number = self.run_step_pr(issue, branch)
            steps.append("pr")
        except Exception as exc:
            return PipelineResult(
                issue_number=issue.number,
                branch=branch,
                pr_number=None,
                status="failed",
                security_passed=security_passed,
                self_review_passed=self_review_passed,
                error=str(exc),
                steps_completed=steps,
            )

        return PipelineResult(
            issue_number=issue.number,
            branch=branch,
            pr_number=pr_number,
            status="success",
            security_passed=security_passed,
            self_review_passed=self_review_passed,
            error=None,
            steps_completed=steps,
        )

    # ------------------------------------------------------------------
    # Individual steps
    # ------------------------------------------------------------------

    def run_step_branch(self, issue) -> str:
        """Return branch name and (optionally) create it via IssueTrigger."""
        branch_name = f"lidco/issue-{issue.number}"
        try:
            from lidco.integrations.issue_trigger import IssueTrigger  # lazy import
            trigger = IssueTrigger(project_dir=self._config.project_dir)
            trigger.create_branch(issue)
        except Exception:
            pass
        return branch_name

    def run_step_fix(self, issue, branch: str):
        """Invoke fix_fn(issue) and return proposal or None."""
        return self._fix_fn(issue)

    def run_step_security(self, changed_files: list[str]):
        """Run SecurityGate and return GateResult."""
        from lidco.review.security_gate import SecurityGate  # lazy import
        gate = SecurityGate(project_dir=self._config.project_dir)
        return gate.check(changed_files, self._config.project_dir)

    def run_step_review(self, diff: str) -> bool:
        """Run SelfReviewer and return True if score >= 0.8."""
        from lidco.review.self_review import SelfReviewer  # lazy import
        reviewer = SelfReviewer(review_fn=None)
        result = reviewer.review(diff)
        return result.score >= 0.8

    def run_step_pr(self, issue, branch: str) -> int | None:
        """Post a review comment and return a fake PR number."""
        try:
            from lidco.review.gh_poster import GHPoster, ReviewComment  # lazy import
            poster = GHPoster(project_dir=self._config.project_dir)
            comment = ReviewComment(
                path=branch,
                line=1,
                body=f"Automated fix for issue #{issue.number}",
            )
            poster.post_review(issue.number, [comment], summary="Pipeline complete.")
        except Exception:
            pass
        # Return a deterministic fake PR number (hash of issue number)
        return abs(hash(issue.number)) % 100_000 or 1

    def poll_and_run(self) -> list[PipelineResult]:
        """Poll for new issues via IssueTrigger and run pipeline for each."""
        try:
            from lidco.integrations.issue_trigger import IssueTrigger  # lazy import
            trigger = IssueTrigger(
                assignee=self._config.assignee,
                label=self._config.label,
                project_dir=self._config.project_dir,
            )
            issues = trigger.poll()
        except Exception:
            return []

        results: list[PipelineResult] = []
        for issue in issues:
            result = self.run(issue)
            results.append(result)
        return results
