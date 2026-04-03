"""Compliance reporting for SOC2, GDPR, and HIPAA frameworks."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ComplianceCheck:
    """A single compliance check result."""

    framework: str
    control: str
    status: str  # "pass", "fail", "warning", "na"
    evidence: str
    recommendation: str = ""


class ComplianceReporter:
    """Run compliance checks against SOC2, GDPR, and HIPAA frameworks."""

    def __init__(self) -> None:
        self._custom_checks: dict[str, list] = {}

    # ------------------------------------------------------------------
    # SOC2
    # ------------------------------------------------------------------

    def check_soc2(self, context: dict) -> list[ComplianceCheck]:
        """Run SOC2 compliance checks."""
        checks: list[ComplianceCheck] = []

        # Access control
        has_auth = context.get("access_control", False)
        checks.append(ComplianceCheck(
            framework="soc2",
            control="access_control",
            status="pass" if has_auth else "fail",
            evidence="Access control enabled" if has_auth else "No access control",
            recommendation="" if has_auth else "Implement role-based access control",
        ))

        # Audit logging
        has_audit = context.get("audit_logging", False)
        checks.append(ComplianceCheck(
            framework="soc2",
            control="audit_logging",
            status="pass" if has_audit else "fail",
            evidence="Audit logging enabled" if has_audit else "No audit logging",
            recommendation="" if has_audit else "Enable comprehensive audit logging",
        ))

        # Encryption
        has_encryption = context.get("encryption", False)
        checks.append(ComplianceCheck(
            framework="soc2",
            control="encryption",
            status="pass" if has_encryption else "fail",
            evidence="Encryption at rest" if has_encryption else "No encryption",
            recommendation="" if has_encryption else "Implement encryption at rest and in transit",
        ))

        # Backup
        has_backup = context.get("backup", False)
        checks.append(ComplianceCheck(
            framework="soc2",
            control="backup",
            status="pass" if has_backup else "warning",
            evidence="Backup configured" if has_backup else "Backup not verified",
            recommendation="" if has_backup else "Configure automated backup and recovery",
        ))

        # Monitoring
        has_monitoring = context.get("monitoring", False)
        checks.append(ComplianceCheck(
            framework="soc2",
            control="monitoring",
            status="pass" if has_monitoring else "warning",
            evidence="Monitoring active" if has_monitoring else "Limited monitoring",
            recommendation="" if has_monitoring else "Set up continuous monitoring",
        ))

        return checks

    # ------------------------------------------------------------------
    # GDPR
    # ------------------------------------------------------------------

    def check_gdpr(self, context: dict) -> list[ComplianceCheck]:
        """Run GDPR compliance checks."""
        checks: list[ComplianceCheck] = []

        # Data minimization
        has_minimization = context.get("data_minimization", False)
        checks.append(ComplianceCheck(
            framework="gdpr",
            control="data_minimization",
            status="pass" if has_minimization else "fail",
            evidence="Data minimization policy" if has_minimization else "No policy",
            recommendation="" if has_minimization else "Implement data minimization",
        ))

        # Consent
        has_consent = context.get("consent", False)
        checks.append(ComplianceCheck(
            framework="gdpr",
            control="consent",
            status="pass" if has_consent else "fail",
            evidence="Consent mechanism" if has_consent else "No consent mechanism",
            recommendation="" if has_consent else "Implement explicit consent collection",
        ))

        # Right to delete
        has_delete = context.get("right_to_delete", False)
        checks.append(ComplianceCheck(
            framework="gdpr",
            control="right_to_delete",
            status="pass" if has_delete else "fail",
            evidence="Deletion workflow" if has_delete else "No deletion workflow",
            recommendation="" if has_delete else "Implement data deletion capability",
        ))

        # Data portability
        has_portability = context.get("data_portability", False)
        checks.append(ComplianceCheck(
            framework="gdpr",
            control="data_portability",
            status="pass" if has_portability else "warning",
            evidence="Export capability" if has_portability else "No export",
            recommendation="" if has_portability else "Implement data export in standard format",
        ))

        # Breach notification
        has_breach_notify = context.get("breach_notification", False)
        checks.append(ComplianceCheck(
            framework="gdpr",
            control="breach_notification",
            status="pass" if has_breach_notify else "fail",
            evidence="72h notification" if has_breach_notify else "No process",
            recommendation="" if has_breach_notify else "Implement 72-hour breach notification",
        ))

        return checks

    # ------------------------------------------------------------------
    # HIPAA
    # ------------------------------------------------------------------

    def check_hipaa(self, context: dict) -> list[ComplianceCheck]:
        """Run HIPAA compliance checks."""
        checks: list[ComplianceCheck] = []

        # PHI protection
        has_phi = context.get("phi_protection", False)
        checks.append(ComplianceCheck(
            framework="hipaa",
            control="phi_protection",
            status="pass" if has_phi else "fail",
            evidence="PHI safeguards" if has_phi else "No PHI safeguards",
            recommendation="" if has_phi else "Implement PHI access controls",
        ))

        # Access audit
        has_access_audit = context.get("access_audit", False)
        checks.append(ComplianceCheck(
            framework="hipaa",
            control="access_audit",
            status="pass" if has_access_audit else "fail",
            evidence="Access audit trail" if has_access_audit else "No audit trail",
            recommendation="" if has_access_audit else "Implement access audit logging",
        ))

        # Encryption
        has_encryption = context.get("encryption", False)
        checks.append(ComplianceCheck(
            framework="hipaa",
            control="encryption",
            status="pass" if has_encryption else "fail",
            evidence="Encryption enabled" if has_encryption else "No encryption",
            recommendation="" if has_encryption else "Encrypt all PHI data",
        ))

        # BAA
        has_baa = context.get("baa", False)
        checks.append(ComplianceCheck(
            framework="hipaa",
            control="baa",
            status="pass" if has_baa else "warning",
            evidence="BAA in place" if has_baa else "No BAA",
            recommendation="" if has_baa else "Establish Business Associate Agreements",
        ))

        return checks

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------

    def run_all(self, context: dict) -> dict[str, list[ComplianceCheck]]:
        """Run all framework checks."""
        return {
            "soc2": self.check_soc2(context),
            "gdpr": self.check_gdpr(context),
            "hipaa": self.check_hipaa(context),
        }

    def gap_analysis(self, context: dict) -> list[ComplianceCheck]:
        """Return only failing checks across all frameworks."""
        all_checks = self.run_all(context)
        gaps: list[ComplianceCheck] = []
        for checks in all_checks.values():
            for check in checks:
                if check.status == "fail":
                    gaps.append(check)
        return gaps

    def export_report(self, context: dict) -> str:
        """Export a full JSON compliance report."""
        all_checks = self.run_all(context)
        report = {
            "timestamp": time.time(),
            "frameworks": {},
        }
        for fw, checks in all_checks.items():
            report["frameworks"][fw] = [
                {
                    "control": c.control,
                    "status": c.status,
                    "evidence": c.evidence,
                    "recommendation": c.recommendation,
                }
                for c in checks
            ]
        return json.dumps(report, indent=2)

    def summary(self, context: dict) -> dict:
        """Return pass/fail/warning counts per framework."""
        all_checks = self.run_all(context)
        result: dict[str, dict[str, int]] = {}
        for fw, checks in all_checks.items():
            counts = {"pass": 0, "fail": 0, "warning": 0, "na": 0}
            for check in checks:
                counts[check.status] = counts.get(check.status, 0) + 1
            result[fw] = counts
        return result
