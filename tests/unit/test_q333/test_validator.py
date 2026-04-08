"""Tests for lidco.adr.validator — ADRValidator."""

from __future__ import annotations

import unittest

from lidco.adr.manager import ADR, ADRManager, ADRStatus
from lidco.adr.validator import (
    ADRValidator,
    ReviewSchedule,
    Severity,
    ValidationIssue,
    ValidationReport,
)


class TestValidationIssue(unittest.TestCase):
    def test_to_dict(self) -> None:
        i = ValidationIssue(adr_number=1, severity=Severity.ERROR, message="bad", rule="completeness")
        d = i.to_dict()
        self.assertEqual(d["severity"], "error")
        self.assertEqual(d["rule"], "completeness")


class TestValidationReport(unittest.TestCase):
    def test_empty(self) -> None:
        r = ValidationReport()
        self.assertTrue(r.passed)
        self.assertEqual(r.error_count, 0)

    def test_counts(self) -> None:
        r = ValidationReport(issues=[
            ValidationIssue(1, Severity.ERROR, "e"),
            ValidationIssue(1, Severity.WARNING, "w"),
            ValidationIssue(1, Severity.INFO, "i"),
        ])
        self.assertEqual(r.error_count, 1)
        self.assertEqual(r.warning_count, 1)
        self.assertEqual(r.info_count, 1)
        self.assertFalse(r.passed)

    def test_to_dict(self) -> None:
        r = ValidationReport(adrs_checked=2, rules_applied=5)
        d = r.to_dict()
        self.assertEqual(d["adrs_checked"], 2)
        self.assertTrue(d["passed"])


class TestReviewSchedule(unittest.TestCase):
    def test_is_due_never_reviewed(self) -> None:
        s = ReviewSchedule(adr_number=1)
        self.assertTrue(s.is_due())

    def test_is_due_overdue(self) -> None:
        s = ReviewSchedule(adr_number=1, review_interval_days=30, last_reviewed="2020-01-01")
        self.assertTrue(s.is_due("2020-06-01"))

    def test_is_due_not_yet(self) -> None:
        s = ReviewSchedule(adr_number=1, review_interval_days=90, last_reviewed="2026-04-01")
        self.assertFalse(s.is_due("2026-04-05"))

    def test_is_due_invalid_date(self) -> None:
        s = ReviewSchedule(adr_number=1, last_reviewed="invalid")
        self.assertTrue(s.is_due())


class TestADRValidator(unittest.TestCase):
    """Tests for ADRValidator."""

    def setUp(self) -> None:
        self.mgr = ADRManager()
        self.validator = ADRValidator(self.mgr)

    def test_validate_completeness_all_present(self) -> None:
        adr = self.mgr.create("T", context="C", decision="D", consequences="E", authors=["A"])
        issues = self.validator.validate_completeness(adr)
        self.assertEqual(len(issues), 0)

    def test_validate_completeness_missing_context(self) -> None:
        adr = self.mgr.create("T", decision="D")
        issues = self.validator.validate_completeness(adr)
        errors = [i for i in issues if i.severity == Severity.ERROR]
        self.assertTrue(any("context" in i.message.lower() for i in errors))

    def test_validate_completeness_missing_decision(self) -> None:
        adr = self.mgr.create("T", context="C")
        issues = self.validator.validate_completeness(adr)
        errors = [i for i in issues if i.severity == Severity.ERROR]
        self.assertTrue(any("decision" in i.message.lower() for i in errors))

    def test_validate_completeness_missing_consequences(self) -> None:
        adr = self.mgr.create("T", context="C", decision="D")
        issues = self.validator.validate_completeness(adr)
        warnings = [i for i in issues if i.severity == Severity.WARNING]
        self.assertTrue(any("consequences" in i.message.lower() for i in warnings))

    def test_validate_completeness_no_authors(self) -> None:
        adr = self.mgr.create("T", context="C", decision="D", consequences="E")
        issues = self.validator.validate_completeness(adr)
        warnings = [i for i in issues if i.severity == Severity.WARNING]
        self.assertTrue(any("authors" in i.message.lower() for i in warnings))

    def test_validate_status_consistency_superseded_no_ref(self) -> None:
        adr = self.mgr.create("T", context="C", decision="D")
        # Manually set status to superseded without superseded_by
        self.mgr.update_status(1, ADRStatus.SUPERSEDED)
        updated = self.mgr.get(1)
        issues = self.validator.validate_status_consistency(updated)
        self.assertTrue(any(i.severity == Severity.ERROR for i in issues))

    def test_validate_status_consistency_ok(self) -> None:
        self.mgr.create("Old", context="C", decision="D")
        self.mgr.create("New", context="C", decision="D")
        self.mgr.supersede(1, 2)
        adr = self.mgr.get(1)
        issues = self.validator.validate_status_consistency(adr)
        self.assertEqual(len(issues), 0)

    def test_validate_code_references_accepted_not_found(self) -> None:
        adr = self.mgr.create("T", context="C", decision="D")
        self.mgr.update_status(1, ADRStatus.ACCEPTED)
        adr = self.mgr.get(1)
        issues = self.validator.validate_code_references(adr, {"a.py": "no refs"})
        self.assertTrue(any("not referenced" in i.message.lower() for i in issues))

    def test_validate_code_references_accepted_found(self) -> None:
        adr = self.mgr.create("T", context="C", decision="D")
        self.mgr.update_status(1, ADRStatus.ACCEPTED)
        adr = self.mgr.get(1)
        issues = self.validator.validate_code_references(adr, {"a.py": "# ADR-1\n"})
        self.assertEqual(len(issues), 0)

    def test_validate_code_references_proposed_skipped(self) -> None:
        adr = self.mgr.create("T")
        issues = self.validator.validate_code_references(adr, {"a.py": "no refs"})
        self.assertEqual(len(issues), 0)

    def test_validate_relevance_overdue(self) -> None:
        adr = self.mgr.create("T", context="C", decision="D")
        self.validator.set_review_schedule(
            ReviewSchedule(adr_number=1, review_interval_days=30, last_reviewed="2020-01-01")
        )
        issues = self.validator.validate_relevance(adr, "2026-04-05")
        self.assertTrue(any("due for review" in i.message.lower() for i in issues))

    def test_validate_relevance_deprecated(self) -> None:
        adr = self.mgr.create("T", context="C", decision="D")
        self.mgr.update_status(1, ADRStatus.DEPRECATED)
        adr = self.mgr.get(1)
        issues = self.validator.validate_relevance(adr)
        self.assertTrue(any("deprecated" in i.message.lower() for i in issues))

    def test_validate_no_contradictions(self) -> None:
        self.mgr.create("A", context="C", decision="Use X", tags=["db"])
        self.mgr.create("B", context="C", decision="Use Y", tags=["db"])
        adr = self.mgr.get(1)
        issues = self.validator.validate_no_contradictions(adr)
        self.assertTrue(any("contradiction" in i.rule for i in issues))

    def test_validate_no_contradictions_different_tags(self) -> None:
        self.mgr.create("A", context="C", decision="Use X", tags=["db"])
        self.mgr.create("B", context="C", decision="Use Y", tags=["api"])
        adr = self.mgr.get(1)
        issues = self.validator.validate_no_contradictions(adr)
        self.assertEqual(len(issues), 0)

    def test_validate_full(self) -> None:
        self.mgr.create("T", context="C", decision="D", consequences="E", authors=["A"])
        report = self.validator.validate()
        self.assertEqual(report.adrs_checked, 1)
        self.assertEqual(report.rules_applied, 5)

    def test_validate_single(self) -> None:
        self.mgr.create("T", context="C", decision="D", consequences="E", authors=["A"])
        report = self.validator.validate_single(1)
        self.assertEqual(report.adrs_checked, 1)

    def test_validate_single_not_found(self) -> None:
        with self.assertRaises(KeyError):
            self.validator.validate_single(99)

    def test_review_schedule_crud(self) -> None:
        s = ReviewSchedule(adr_number=1, review_interval_days=60)
        self.validator.set_review_schedule(s)
        self.assertIsNotNone(self.validator.get_review_schedule(1))
        self.assertIsNone(self.validator.get_review_schedule(99))

    def test_get_overdue_reviews(self) -> None:
        self.validator.set_review_schedule(
            ReviewSchedule(adr_number=1, review_interval_days=30, last_reviewed="2020-01-01")
        )
        overdue = self.validator.get_overdue_reviews("2026-04-05")
        self.assertEqual(len(overdue), 1)

    def test_manager_property(self) -> None:
        self.assertIs(self.validator.manager, self.mgr)


if __name__ == "__main__":
    unittest.main()
