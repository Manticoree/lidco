"""Migration Advisor — advise on legacy migration with risk assessment.

Provides ``MigrationAdvisor`` that evaluates a codebase snapshot and
produces an incremental migration strategy with risk scoring, parallel
running advice, and testing recommendations.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class RiskLevel(enum.Enum):
    """Migration risk level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class MigrationRisk:
    """A single identified migration risk."""

    description: str
    level: RiskLevel
    mitigation: str
    affected_files: tuple[str, ...] = ()

    def is_blocking(self) -> bool:
        return self.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


@dataclass(frozen=True)
class MigrationStep:
    """One step in an incremental migration plan."""

    order: int
    title: str
    description: str
    files: tuple[str, ...] = ()
    risks: tuple[MigrationRisk, ...] = ()
    parallel_safe: bool = True
    test_strategy: str = ""

    @property
    def risk_count(self) -> int:
        return len(self.risks)

    def has_blocking_risks(self) -> bool:
        return any(r.is_blocking() for r in self.risks)


@dataclass
class MigrationPlan:
    """Complete migration plan with steps and overall assessment."""

    name: str
    steps: list[MigrationStep] = field(default_factory=list)
    overall_risk: RiskLevel = RiskLevel.LOW

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def total_files(self) -> int:
        seen: set[str] = set()
        for step in self.steps:
            seen.update(step.files)
        return len(seen)

    @property
    def blocking_count(self) -> int:
        return sum(1 for s in self.steps if s.has_blocking_risks())

    def summary(self) -> str:
        lines = [
            f"Migration Plan: {self.name}",
            f"Steps: {self.step_count}, Files: {self.total_files}, "
            f"Overall risk: {self.overall_risk.value}",
        ]
        for step in self.steps:
            risk_tag = " [BLOCKING]" if step.has_blocking_risks() else ""
            par_tag = " (parallel-safe)" if step.parallel_safe else " (sequential)"
            lines.append(
                f"  {step.order}. {step.title}{risk_tag}{par_tag}"
            )
            if step.test_strategy:
                lines.append(f"     Test: {step.test_strategy}")
        return "\n".join(lines)


class MigrationAdvisor:
    """Advise on legacy code migration.

    Parameters
    ----------
    files:
        Mapping of file path to source content for analysis.
    """

    def __init__(self, files: dict[str, str] | None = None) -> None:
        self._files: dict[str, str] = dict(files) if files else {}

    @property
    def file_count(self) -> int:
        return len(self._files)

    def add_file(self, path: str, content: str) -> None:
        self._files[path] = content

    def assess_risks(self) -> list[MigrationRisk]:
        """Scan files and return identified risks."""
        risks: list[MigrationRisk] = []
        for path, content in self._files.items():
            lines = content.splitlines()
            line_count = len(lines)
            # Large file risk
            if line_count > 500:
                risks.append(
                    MigrationRisk(
                        description=f"Large file ({line_count} lines)",
                        level=RiskLevel.MEDIUM,
                        mitigation="Split into smaller modules before migrating",
                        affected_files=(path,),
                    )
                )
            # Global state
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("global "):
                    risks.append(
                        MigrationRisk(
                            description="Global mutable state",
                            level=RiskLevel.HIGH,
                            mitigation="Refactor to explicit parameter passing",
                            affected_files=(path,),
                        )
                    )
                    break  # one per file
            # Dynamic execution
            if any("eval(" in l or "exec(" in l for l in lines):
                risks.append(
                    MigrationRisk(
                        description="Dynamic code execution",
                        level=RiskLevel.CRITICAL,
                        mitigation="Replace eval/exec with safe alternatives",
                        affected_files=(path,),
                    )
                )
        return risks

    def plan(self, name: str = "migration") -> MigrationPlan:
        """Generate a migration plan for the loaded files."""
        risks = self.assess_risks()
        # Group files by risk level
        critical_files: list[str] = []
        normal_files: list[str] = []
        for path in self._files:
            file_risks = [r for r in risks if path in r.affected_files]
            if any(r.is_blocking() for r in file_risks):
                critical_files.append(path)
            else:
                normal_files.append(path)

        steps: list[MigrationStep] = []
        order = 1

        # Step 1: always start with tests
        steps.append(
            MigrationStep(
                order=order,
                title="Add characterisation tests",
                description="Write tests capturing current behaviour before any changes",
                files=tuple(sorted(self._files.keys())),
                parallel_safe=True,
                test_strategy="Run full test suite, verify baseline passes",
            )
        )
        order += 1

        # Step 2: address critical files first
        if critical_files:
            crit_risks = tuple(r for r in risks if r.is_blocking())
            steps.append(
                MigrationStep(
                    order=order,
                    title="Address critical-risk files",
                    description="Fix blocking issues before broader migration",
                    files=tuple(sorted(critical_files)),
                    risks=crit_risks,
                    parallel_safe=False,
                    test_strategy="Targeted tests for each critical change",
                )
            )
            order += 1

        # Step 3: migrate normal files
        if normal_files:
            norm_risks = tuple(r for r in risks if not r.is_blocking())
            steps.append(
                MigrationStep(
                    order=order,
                    title="Migrate remaining files",
                    description="Incremental migration of lower-risk modules",
                    files=tuple(sorted(normal_files)),
                    risks=norm_risks,
                    parallel_safe=True,
                    test_strategy="Parallel run: old and new code side-by-side",
                )
            )
            order += 1

        # Step 4: cleanup
        steps.append(
            MigrationStep(
                order=order,
                title="Remove legacy code",
                description="Delete old implementations after parallel-run period",
                files=tuple(sorted(self._files.keys())),
                parallel_safe=True,
                test_strategy="Full regression suite",
            )
        )

        # Overall risk
        if any(r.level == RiskLevel.CRITICAL for r in risks):
            overall = RiskLevel.CRITICAL
        elif any(r.level == RiskLevel.HIGH for r in risks):
            overall = RiskLevel.HIGH
        elif any(r.level == RiskLevel.MEDIUM for r in risks):
            overall = RiskLevel.MEDIUM
        else:
            overall = RiskLevel.LOW

        return MigrationPlan(name=name, steps=steps, overall_risk=overall)
