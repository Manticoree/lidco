"""ADR Validator — validate ADR compliance and relevance.

Checks that ADRs are referenced in code, not contradicted, still relevant,
and have review schedules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from lidco.adr.manager import ADR, ADRManager, ADRStatus
from lidco.adr.search import ADRSearch, CodeReference


class Severity:
    """Validation issue severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A single validation issue found."""

    adr_number: int
    severity: str  # Severity constant
    message: str
    rule: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "adr_number": self.adr_number,
            "severity": self.severity,
            "message": self.message,
            "rule": self.rule,
        }


@dataclass
class ValidationReport:
    """Overall validation report."""

    issues: list[ValidationIssue] = field(default_factory=list)
    adrs_checked: int = 0
    rules_applied: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.INFO)

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "issues": [i.to_dict() for i in self.issues],
            "adrs_checked": self.adrs_checked,
            "rules_applied": self.rules_applied,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "passed": self.passed,
        }


@dataclass
class ReviewSchedule:
    """Review schedule for an ADR."""

    adr_number: int
    review_interval_days: int = 90
    last_reviewed: str = ""

    def is_due(self, current_date: str = "") -> bool:
        """Check if review is due."""
        if not self.last_reviewed:
            return True
        if not current_date:
            current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            last = datetime.strptime(self.last_reviewed, "%Y-%m-%d")
            now = datetime.strptime(current_date, "%Y-%m-%d")
            delta = (now - last).days
            return delta >= self.review_interval_days
        except ValueError:
            return True


class ADRValidator:
    """Validate ADR compliance, relevance, and consistency."""

    def __init__(self, manager: ADRManager) -> None:
        self._manager = manager
        self._search = ADRSearch(manager)
        self._review_schedules: dict[int, ReviewSchedule] = {}

    @property
    def manager(self) -> ADRManager:
        return self._manager

    # -- Review schedules ----------------------------------------------------

    def set_review_schedule(self, schedule: ReviewSchedule) -> None:
        """Set a review schedule for an ADR."""
        self._review_schedules[schedule.adr_number] = schedule

    def get_review_schedule(self, adr_number: int) -> ReviewSchedule | None:
        """Get the review schedule for an ADR."""
        return self._review_schedules.get(adr_number)

    def get_overdue_reviews(self, current_date: str = "") -> list[ReviewSchedule]:
        """Get ADRs with overdue reviews."""
        return [
            s for s in self._review_schedules.values()
            if s.is_due(current_date)
        ]

    # -- Validation rules ----------------------------------------------------

    def validate_completeness(self, adr: ADR) -> list[ValidationIssue]:
        """Check that required ADR sections are filled in."""
        issues: list[ValidationIssue] = []
        if not adr.context.strip():
            issues.append(ValidationIssue(
                adr_number=adr.number,
                severity=Severity.ERROR,
                message="Missing context section",
                rule="completeness",
            ))
        if not adr.decision.strip():
            issues.append(ValidationIssue(
                adr_number=adr.number,
                severity=Severity.ERROR,
                message="Missing decision section",
                rule="completeness",
            ))
        if not adr.consequences.strip():
            issues.append(ValidationIssue(
                adr_number=adr.number,
                severity=Severity.WARNING,
                message="Missing consequences section",
                rule="completeness",
            ))
        if not adr.authors:
            issues.append(ValidationIssue(
                adr_number=adr.number,
                severity=Severity.WARNING,
                message="No authors listed",
                rule="completeness",
            ))
        return issues

    def validate_status_consistency(self, adr: ADR) -> list[ValidationIssue]:
        """Validate status field consistency."""
        issues: list[ValidationIssue] = []
        if adr.status == ADRStatus.SUPERSEDED and adr.superseded_by is None:
            issues.append(ValidationIssue(
                adr_number=adr.number,
                severity=Severity.ERROR,
                message="Status is 'superseded' but no superseding ADR is referenced",
                rule="status_consistency",
            ))
        if adr.superseded_by is not None and adr.status != ADRStatus.SUPERSEDED:
            issues.append(ValidationIssue(
                adr_number=adr.number,
                severity=Severity.WARNING,
                message="Has superseded_by reference but status is not 'superseded'",
                rule="status_consistency",
            ))
        return issues

    def validate_code_references(
        self,
        adr: ADR,
        file_contents: dict[str, str],
    ) -> list[ValidationIssue]:
        """Check that an accepted ADR is referenced in code."""
        issues: list[ValidationIssue] = []
        if adr.status != ADRStatus.ACCEPTED:
            return issues

        refs = self._search.find_code_references(file_contents)
        adr_refs = [r for r in refs if r.adr_number == adr.number]
        if not adr_refs:
            issues.append(ValidationIssue(
                adr_number=adr.number,
                severity=Severity.WARNING,
                message="Accepted ADR not referenced in any code file",
                rule="code_reference",
            ))
        return issues

    def validate_relevance(self, adr: ADR, current_date: str = "") -> list[ValidationIssue]:
        """Check if an ADR might be stale or needs review."""
        issues: list[ValidationIssue] = []
        schedule = self._review_schedules.get(adr.number)
        if schedule and schedule.is_due(current_date):
            issues.append(ValidationIssue(
                adr_number=adr.number,
                severity=Severity.INFO,
                message="ADR is due for review",
                rule="relevance",
            ))
        # Deprecated ADRs still referenced might be a problem
        if adr.status == ADRStatus.DEPRECATED:
            issues.append(ValidationIssue(
                adr_number=adr.number,
                severity=Severity.INFO,
                message="ADR is deprecated — consider removing references",
                rule="relevance",
            ))
        return issues

    def validate_no_contradictions(self, adr: ADR) -> list[ValidationIssue]:
        """Check for potential contradictions with other ADRs."""
        issues: list[ValidationIssue] = []
        if adr.status not in (ADRStatus.ACCEPTED, ADRStatus.PROPOSED):
            return issues

        for other in self._manager.list_all():
            if other.number == adr.number:
                continue
            if other.status not in (ADRStatus.ACCEPTED, ADRStatus.PROPOSED):
                continue
            # Simple heuristic: same tags might indicate overlap
            common_tags = set(adr.tags) & set(other.tags)
            if common_tags and adr.decision and other.decision:
                issues.append(ValidationIssue(
                    adr_number=adr.number,
                    severity=Severity.INFO,
                    message=(
                        f"Shares tags {common_tags} with ADR-{other.number:04d} — "
                        "verify decisions are not contradictory"
                    ),
                    rule="contradiction",
                ))
        return issues

    # -- Full validation -----------------------------------------------------

    def validate(
        self,
        *,
        file_contents: dict[str, str] | None = None,
        current_date: str = "",
    ) -> ValidationReport:
        """Run all validation rules on all ADRs."""
        report = ValidationReport()
        adrs = self._manager.list_all()
        report.adrs_checked = len(adrs)
        report.rules_applied = 5  # completeness, status, code_ref, relevance, contradiction

        for adr in adrs:
            report.issues.extend(self.validate_completeness(adr))
            report.issues.extend(self.validate_status_consistency(adr))
            if file_contents:
                report.issues.extend(self.validate_code_references(adr, file_contents))
            report.issues.extend(self.validate_relevance(adr, current_date))
            report.issues.extend(self.validate_no_contradictions(adr))

        return report

    def validate_single(
        self,
        number: int,
        *,
        file_contents: dict[str, str] | None = None,
        current_date: str = "",
    ) -> ValidationReport:
        """Validate a single ADR."""
        adr = self._manager.get(number)
        if adr is None:
            raise KeyError(f"ADR-{number:04d} not found")
        report = ValidationReport(adrs_checked=1, rules_applied=5)
        report.issues.extend(self.validate_completeness(adr))
        report.issues.extend(self.validate_status_consistency(adr))
        if file_contents:
            report.issues.extend(self.validate_code_references(adr, file_contents))
        report.issues.extend(self.validate_relevance(adr, current_date))
        report.issues.extend(self.validate_no_contradictions(adr))
        return report
