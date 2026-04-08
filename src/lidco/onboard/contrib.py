"""Contribution Guide — generate contribution guide with workflow, conventions,
testing, PR process, and common pitfalls.

Part of Q330 — Onboarding Intelligence (task 1765).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class WorkflowStep:
    """A step in the contribution workflow."""

    name: str
    description: str
    command: str = ""
    order: int = 0


@dataclass(frozen=True)
class Convention:
    """A coding or project convention."""

    name: str
    description: str
    example: str = ""
    category: str = "general"


@dataclass(frozen=True)
class Pitfall:
    """A common pitfall for contributors."""

    name: str
    description: str
    fix: str = ""
    severity: str = "medium"


@dataclass(frozen=True)
class PRTemplate:
    """A pull request template."""

    title_format: str
    body_template: str
    labels: List[str] = field(default_factory=list)
    checklist: List[str] = field(default_factory=list)


@dataclass
class ContributionGuide:
    """Generated contribution guide."""

    project_name: str
    workflow: List[WorkflowStep] = field(default_factory=list)
    conventions: List[Convention] = field(default_factory=list)
    testing_instructions: str = ""
    pr_template: Optional[PRTemplate] = None
    pitfalls: List[Pitfall] = field(default_factory=list)

    def render(self) -> str:
        """Render the full guide as text."""
        lines = [f"# Contributing to {self.project_name}", ""]

        if self.workflow:
            lines.append("## Workflow")
            for step in sorted(self.workflow, key=lambda s: s.order):
                cmd = f" (`{step.command}`)" if step.command else ""
                lines.append(f"{step.order}. **{step.name}** — {step.description}{cmd}")
            lines.append("")

        if self.conventions:
            lines.append("## Conventions")
            for conv in self.conventions:
                lines.append(f"- **{conv.name}** ({conv.category}): {conv.description}")
                if conv.example:
                    lines.append(f"  Example: `{conv.example}`")
            lines.append("")

        if self.testing_instructions:
            lines.append("## Testing")
            lines.append(self.testing_instructions)
            lines.append("")

        if self.pr_template:
            lines.append("## Pull Request Process")
            lines.append(f"Title format: `{self.pr_template.title_format}`")
            if self.pr_template.labels:
                lines.append(f"Labels: {', '.join(self.pr_template.labels)}")
            if self.pr_template.checklist:
                lines.append("Checklist:")
                for item in self.pr_template.checklist:
                    lines.append(f"  - [ ] {item}")
            lines.append("")

        if self.pitfalls:
            lines.append("## Common Pitfalls")
            for p in self.pitfalls:
                lines.append(f"- **{p.name}** [{p.severity}]: {p.description}")
                if p.fix:
                    lines.append(f"  Fix: {p.fix}")
            lines.append("")

        return "\n".join(lines)


class ContributionGuideGenerator:
    """Generate contribution guides from project analysis."""

    def __init__(self, project_name: str = "project") -> None:
        self._project_name = project_name
        self._workflow_steps: List[WorkflowStep] = []
        self._conventions: List[Convention] = []
        self._pitfalls: List[Pitfall] = []
        self._testing_instructions: str = ""
        self._pr_template: Optional[PRTemplate] = None

    @property
    def project_name(self) -> str:
        return self._project_name

    def add_workflow_step(self, step: WorkflowStep) -> None:
        """Add a workflow step."""
        self._workflow_steps = [*self._workflow_steps, step]

    def add_workflow_steps(self, steps: Sequence[WorkflowStep]) -> None:
        """Add multiple workflow steps."""
        for s in steps:
            self.add_workflow_step(s)

    def add_convention(self, convention: Convention) -> None:
        """Add a convention."""
        self._conventions = [*self._conventions, convention]

    def add_conventions(self, conventions: Sequence[Convention]) -> None:
        """Add multiple conventions."""
        for c in conventions:
            self.add_convention(c)

    def add_pitfall(self, pitfall: Pitfall) -> None:
        """Add a common pitfall."""
        self._pitfalls = [*self._pitfalls, pitfall]

    def add_pitfalls(self, pitfalls: Sequence[Pitfall]) -> None:
        """Add multiple pitfalls."""
        for p in pitfalls:
            self.add_pitfall(p)

    def set_testing_instructions(self, instructions: str) -> None:
        """Set testing instructions."""
        self._testing_instructions = instructions

    def set_pr_template(self, template: PRTemplate) -> None:
        """Set the PR template."""
        self._pr_template = template

    def generate(self) -> ContributionGuide:
        """Generate the contribution guide."""
        return ContributionGuide(
            project_name=self._project_name,
            workflow=list(self._workflow_steps),
            conventions=list(self._conventions),
            testing_instructions=self._testing_instructions,
            pr_template=self._pr_template,
            pitfalls=list(self._pitfalls),
        )

    def generate_default(self) -> ContributionGuide:
        """Generate a contribution guide with sensible defaults."""
        default_workflow = [
            WorkflowStep(name="Fork", description="Fork the repository", order=1),
            WorkflowStep(
                name="Branch",
                description="Create a feature branch",
                command="git checkout -b feat/my-feature",
                order=2,
            ),
            WorkflowStep(
                name="Develop",
                description="Make your changes following conventions",
                order=3,
            ),
            WorkflowStep(
                name="Test",
                description="Run tests to verify",
                command="python -m pytest -q",
                order=4,
            ),
            WorkflowStep(
                name="Commit",
                description="Commit with conventional message",
                command="git commit -m 'feat: description'",
                order=5,
            ),
            WorkflowStep(
                name="Push",
                description="Push and open PR",
                command="git push -u origin feat/my-feature",
                order=6,
            ),
        ]
        default_conventions = [
            Convention(
                name="Conventional Commits",
                description="Use feat/fix/refactor/docs/test prefixes",
                example="feat: add new feature",
                category="git",
            ),
            Convention(
                name="Type Hints",
                description="Use type annotations on all public functions",
                category="code",
            ),
            Convention(
                name="Small Files",
                description="Keep files under 800 lines",
                category="code",
            ),
        ]
        default_pitfalls = [
            Pitfall(
                name="Missing Tests",
                description="All features must have tests",
                fix="Write tests before or alongside code",
                severity="high",
            ),
            Pitfall(
                name="Large PRs",
                description="PRs over 500 lines are hard to review",
                fix="Break into smaller focused PRs",
                severity="medium",
            ),
        ]
        default_pr = PRTemplate(
            title_format="<type>: <short description>",
            body_template="## Summary\n\n## Test plan\n",
            labels=["needs-review"],
            checklist=["Tests pass", "No lint errors", "Docs updated"],
        )
        return ContributionGuide(
            project_name=self._project_name,
            workflow=default_workflow,
            conventions=default_conventions,
            testing_instructions="Run `python -m pytest -q` to execute the test suite.",
            pr_template=default_pr,
            pitfalls=default_pitfalls,
        )

    def summary(self) -> str:
        """Return a human-readable summary."""
        return (
            f"Contribution Guide Generator: {self._project_name}\n"
            f"Workflow steps: {len(self._workflow_steps)}\n"
            f"Conventions: {len(self._conventions)}\n"
            f"Pitfalls: {len(self._pitfalls)}\n"
            f"PR template: {'set' if self._pr_template else 'not set'}"
        )
