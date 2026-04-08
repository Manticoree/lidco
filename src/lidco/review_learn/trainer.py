"""Review Trainer — Practice code review with sample PRs (Q332, task 1773)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Difficulty(Enum):
    """Difficulty level for a training exercise."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class ReviewIssue:
    """An issue that should be found during review."""

    description: str
    line: int
    severity: str = "warning"
    hint: str = ""


@dataclass(frozen=True)
class SamplePR:
    """A sample pull request for review training."""

    pr_id: str
    title: str
    description: str
    diff: str
    language: str
    difficulty: Difficulty
    issues: tuple[ReviewIssue, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def issue_count(self) -> int:
        return len(self.issues)


@dataclass
class ReviewSubmission:
    """A trainee's review submission for a sample PR."""

    pr_id: str
    found_issues: list[str] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    submitted_at: float = 0.0

    def __post_init__(self) -> None:
        if self.submitted_at == 0.0:
            self.submitted_at = time.time()


@dataclass(frozen=True)
class TrainingScore:
    """Score for a review training session."""

    pr_id: str
    issues_found: int
    issues_total: int
    precision: float
    recall: float
    score: float
    feedback: str

    @property
    def grade(self) -> str:
        if self.score >= 90:
            return "A"
        if self.score >= 80:
            return "B"
        if self.score >= 70:
            return "C"
        if self.score >= 60:
            return "D"
        return "F"


class ReviewTrainer:
    """Manages review training exercises and scoring."""

    def __init__(self) -> None:
        self._samples: dict[str, SamplePR] = {}
        self._submissions: list[ReviewSubmission] = []
        self._scores: list[TrainingScore] = []

    def add_sample(self, sample: SamplePR) -> None:
        """Add a sample PR for training."""
        self._samples = {**self._samples, sample.pr_id: sample}

    def remove_sample(self, pr_id: str) -> bool:
        if pr_id not in self._samples:
            return False
        self._samples = {k: v for k, v in self._samples.items() if k != pr_id}
        return True

    def get_sample(self, pr_id: str) -> SamplePR | None:
        return self._samples.get(pr_id)

    def list_samples(self, difficulty: Difficulty | None = None) -> list[SamplePR]:
        """List samples, optionally filtered by difficulty."""
        samples = list(self._samples.values())
        if difficulty is not None:
            samples = [s for s in samples if s.difficulty == difficulty]
        return sorted(samples, key=lambda s: s.pr_id)

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def submit_review(self, submission: ReviewSubmission) -> TrainingScore:
        """Score a trainee's review submission against expert issues."""
        sample = self._samples.get(submission.pr_id)
        if sample is None:
            raise ValueError(f"Unknown sample PR: {submission.pr_id}")

        self._submissions = [*self._submissions, submission]

        expert_descs = {issue.description.lower() for issue in sample.issues}
        found_descs = {desc.lower() for desc in submission.found_issues}

        true_positives = len(expert_descs & found_descs)
        issues_total = len(expert_descs)
        issues_found = true_positives

        precision = true_positives / len(found_descs) if found_descs else 0.0
        recall = true_positives / issues_total if issues_total else 1.0
        score = (precision * 50 + recall * 50) if issues_total else 100.0

        missed = expert_descs - found_descs
        false_pos = found_descs - expert_descs

        feedback_parts: list[str] = []
        if missed:
            feedback_parts.append(f"Missed issues: {', '.join(sorted(missed))}")
        if false_pos:
            feedback_parts.append(f"False positives: {', '.join(sorted(false_pos))}")
        if not missed and not false_pos:
            feedback_parts.append("Perfect review!")
        feedback = "; ".join(feedback_parts)

        ts = TrainingScore(
            pr_id=submission.pr_id,
            issues_found=issues_found,
            issues_total=issues_total,
            precision=round(precision, 4),
            recall=round(recall, 4),
            score=round(score, 2),
            feedback=feedback,
        )
        self._scores = [*self._scores, ts]
        return ts

    def get_scores(self, pr_id: str | None = None) -> list[TrainingScore]:
        """Get training scores, optionally filtered by PR."""
        if pr_id is not None:
            return [s for s in self._scores if s.pr_id == pr_id]
        return list(self._scores)

    def average_score(self) -> float:
        """Return average score across all submissions."""
        if not self._scores:
            return 0.0
        return round(sum(s.score for s in self._scores) / len(self._scores), 2)

    def guided_hints(self, pr_id: str) -> list[str]:
        """Return progressive hints for a sample PR."""
        sample = self._samples.get(pr_id)
        if sample is None:
            return []
        hints: list[str] = []
        for issue in sample.issues:
            if issue.hint:
                hints.append(issue.hint)
            else:
                hints.append(f"Look at line {issue.line} for a {issue.severity} issue")
        return hints


def create_default_trainer() -> ReviewTrainer:
    """Create a trainer with built-in sample PRs."""
    trainer = ReviewTrainer()
    trainer.add_sample(SamplePR(
        pr_id="sample-001",
        title="Add user authentication",
        description="Implements basic auth with JWT",
        diff="+ API_KEY = 'sk-secret-123'\n+ except Exception:\n+     pass",
        language="python",
        difficulty=Difficulty.BEGINNER,
        issues=(
            ReviewIssue("hardcoded secret", line=1, severity="critical", hint="Check for hardcoded credentials"),
            ReviewIssue("broad except", line=2, severity="error", hint="Look at error handling"),
        ),
        tags=("security", "error-handling"),
    ))
    trainer.add_sample(SamplePR(
        pr_id="sample-002",
        title="Optimize database queries",
        description="Refactor user listing endpoint",
        diff="+ for user in users:\n+     orders = db.query(user.id)\n+     user.orders = orders",
        language="python",
        difficulty=Difficulty.INTERMEDIATE,
        issues=(
            ReviewIssue("n+1 query", line=1, severity="error", hint="Count the database calls"),
            ReviewIssue("mutation", line=3, severity="warning", hint="Check for in-place mutation"),
        ),
        tags=("performance", "immutability"),
    ))
    return trainer
