"""Dependency audit against advisory DB."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from lidco.sec_intel.vuln_scanner import Severity


@dataclass(frozen=True)
class Advisory:
    """A known vulnerability advisory for a package version."""

    package: str
    version: str
    cve: str = ""
    severity: Severity = Severity.MEDIUM
    description: str = ""
    fix_version: str = ""


class DepAuditor:
    """Audit dependencies against a local advisory database."""

    def __init__(self) -> None:
        self._advisories: list[Advisory] = []

    def add_advisory(self, advisory: Advisory) -> None:
        """Add an advisory to the database."""
        self._advisories.append(advisory)

    def parse_requirements(self, text: str) -> list[tuple[str, str]]:
        """Parse ``pkg==version`` lines from requirements text.

        Lines that don't match the ``name==version`` pattern are ignored.
        """
        results: list[tuple[str, str]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "==" in line:
                parts = line.split("==", 1)
                name = parts[0].strip()
                version = parts[1].strip()
                if name and version:
                    results.append((name, version))
        return results

    def audit(self, requirements: list[tuple[str, str]]) -> list[Advisory]:
        """Return advisories matching any of *requirements*."""
        findings: list[Advisory] = []
        for pkg, ver in requirements:
            for adv in self._advisories:
                if adv.package.lower() == pkg.lower() and adv.version == ver:
                    findings.append(adv)
        return findings

    def has_vulnerability(self, package: str, version: str) -> bool:
        """Check if a specific package version has any advisory."""
        for adv in self._advisories:
            if adv.package.lower() == package.lower() and adv.version == version:
                return True
        return False

    def upgrade_recommendations(self, findings: list[Advisory]) -> list[str]:
        """Return upgrade recommendation strings for advisories that have a fix_version."""
        recs: list[str] = []
        for adv in findings:
            if adv.fix_version:
                recs.append(f"Upgrade {adv.package} from {adv.version} to {adv.fix_version}")
        return recs

    def summary(self, findings: list[Advisory]) -> str:
        """Return a human-readable summary of audit *findings*."""
        if not findings:
            return "No vulnerable dependencies found."
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
        lines = [f"Vulnerable dependencies: {len(findings)}"]
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            if sev in counts:
                lines.append(f"  {sev}: {counts[sev]}")
        return "\n".join(lines)
