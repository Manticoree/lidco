"""Multi-agent PR review pipeline — Task 1042."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class ReviewSeverity(Enum):
    """Severity levels for review issues."""

    CRITICAL = "critical"
    IMPORTANT = "important"
    SUGGESTION = "suggestion"


@dataclass(frozen=True)
class ReviewIssue:
    """A single review issue found by an agent."""

    severity: ReviewSeverity
    category: str
    file: str
    line: int
    message: str
    agent_name: str


@dataclass
class ReviewReport:
    """Aggregated report from a pipeline run."""

    agents_run: list[str] = field(default_factory=list)
    issues: list[ReviewIssue] = field(default_factory=list)
    summary: str = ""
    duration_ms: float = 0.0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity is ReviewSeverity.CRITICAL)

    @property
    def important_count(self) -> int:
        return sum(1 for i in self.issues if i.severity is ReviewSeverity.IMPORTANT)

    @property
    def suggestion_count(self) -> int:
        return sum(1 for i in self.issues if i.severity is ReviewSeverity.SUGGESTION)

    def issues_by_severity(self, severity: ReviewSeverity) -> list[ReviewIssue]:
        return [i for i in self.issues if i.severity is severity]

    def issues_by_agent(self, agent_name: str) -> list[ReviewIssue]:
        return [i for i in self.issues if i.agent_name == agent_name]

    def format(self) -> str:
        if not self.issues:
            return "No review issues found."
        lines = [
            f"Review complete: {len(self.issues)} issue(s) "
            f"({self.critical_count} critical, {self.important_count} important, "
            f"{self.suggestion_count} suggestion) in {self.duration_ms:.0f}ms",
            f"Agents: {', '.join(self.agents_run)}",
            "",
        ]
        for issue in self.issues:
            loc = f"{issue.file}:{issue.line}" if issue.file else f"line {issue.line}"
            lines.append(
                f"  [{issue.severity.value.upper()}] {loc} "
                f"({issue.agent_name}/{issue.category}) {issue.message}"
            )
        return "\n".join(lines)


class ReviewAgent(ABC):
    """Abstract base for review agents."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent display name."""

    @abstractmethod
    def analyze(self, diff: str, files: Sequence[str]) -> list[ReviewIssue]:
        """Analyze diff and return issues."""


class ReviewPipeline:
    """Builder-pattern pipeline that runs review agents on a diff."""

    def __init__(
        self,
        diff_text: str,
        changed_files: Sequence[str],
        agents: tuple[ReviewAgent, ...] = (),
    ) -> None:
        self._diff_text = diff_text
        self._changed_files = tuple(changed_files)
        self._agents = agents

    @property
    def diff_text(self) -> str:
        return self._diff_text

    @property
    def changed_files(self) -> tuple[str, ...]:
        return self._changed_files

    @property
    def agents(self) -> tuple[ReviewAgent, ...]:
        return self._agents

    def add_agent(self, agent: ReviewAgent) -> ReviewPipeline:
        """Return a new pipeline with the agent appended (immutable)."""
        return ReviewPipeline(
            diff_text=self._diff_text,
            changed_files=self._changed_files,
            agents=(*self._agents, agent),
        )

    def run_sequential(self) -> ReviewReport:
        """Run all agents sequentially."""
        return self._execute()

    def run_parallel(self) -> ReviewReport:
        """Run all agents (parallel stub — runs sequentially for stdlib)."""
        return self._execute()

    def run(self, mode: str = "parallel") -> ReviewReport:
        """Run pipeline in the given mode ('parallel' or 'sequential')."""
        if mode == "sequential":
            return self.run_sequential()
        return self.run_parallel()

    def _execute(self) -> ReviewReport:
        start = time.monotonic()
        all_issues: list[ReviewIssue] = []
        agents_run: list[str] = []

        for agent in self._agents:
            agents_run.append(agent.name)
            try:
                issues = agent.analyze(self._diff_text, list(self._changed_files))
                all_issues.extend(issues)
            except Exception:
                # Agent failure should not break the pipeline
                pass

        elapsed_ms = (time.monotonic() - start) * 1000.0

        # Sort: critical first, then important, then suggestion
        severity_order = {
            ReviewSeverity.CRITICAL: 0,
            ReviewSeverity.IMPORTANT: 1,
            ReviewSeverity.SUGGESTION: 2,
        }
        sorted_issues = sorted(all_issues, key=lambda i: severity_order.get(i.severity, 9))

        report = ReviewReport(
            agents_run=agents_run,
            issues=sorted_issues,
            duration_ms=elapsed_ms,
        )
        report.summary = report.format()
        return report
