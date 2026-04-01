"""OWASP vulnerability pattern scanner."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List


class Severity(str, Enum):
    """Vulnerability severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass(frozen=True)
class VulnFinding:
    """A single vulnerability finding."""

    rule: str
    file: str
    line: int = 0
    severity: Severity = Severity.MEDIUM
    description: str = ""
    fix_suggestion: str = ""
    cwe: str = ""


class VulnScanner:
    """OWASP vulnerability pattern scanner."""

    def __init__(self) -> None:
        self._custom_rules: list[dict[str, object]] = []

    def scan(self, source: str, file: str = "") -> list[VulnFinding]:
        """Check all built-in and custom patterns against *source*."""
        findings: list[VulnFinding] = []
        findings.extend(self._check_sql_injection(source, file))
        findings.extend(self._check_xss(source, file))
        findings.extend(self._check_path_traversal(source, file))
        findings.extend(self._check_hardcoded_secrets(source, file))
        findings.extend(self._check_custom_rules(source, file))
        return findings

    # ------------------------------------------------------------------
    # Built-in checks
    # ------------------------------------------------------------------

    def _check_sql_injection(self, source: str, file: str) -> list[VulnFinding]:
        findings: list[VulnFinding] = []
        patterns = [
            re.compile(r"""(?:execute|cursor\.execute)\s*\(\s*(?:f['\"]|['\"].*%s|.*\.format\()"""),
            re.compile(r"""(?:execute|cursor\.execute)\s*\(\s*['\"].*\+"""),
        ]
        for i, line in enumerate(source.splitlines(), 1):
            for pat in patterns:
                if pat.search(line):
                    findings.append(VulnFinding(
                        rule="sql-injection",
                        file=file,
                        line=i,
                        severity=Severity.CRITICAL,
                        description="Possible SQL injection via string interpolation",
                        fix_suggestion="Use parameterized queries with placeholders",
                        cwe="CWE-89",
                    ))
                    break
        return findings

    def _check_xss(self, source: str, file: str) -> list[VulnFinding]:
        findings: list[VulnFinding] = []
        patterns = [
            re.compile(r"""innerHTML\s*=\s*[^'\"]\S*"""),
            re.compile(r"""document\.write\s*\("""),
            re.compile(r"""\.html\s*\(\s*[^'\"]"""),
            re.compile(r"""\beval\s*\("""),
        ]
        for i, line in enumerate(source.splitlines(), 1):
            for pat in patterns:
                if pat.search(line):
                    findings.append(VulnFinding(
                        rule="xss",
                        file=file,
                        line=i,
                        severity=Severity.HIGH,
                        description="Possible cross-site scripting (XSS) vulnerability",
                        fix_suggestion="Sanitize user input before rendering",
                        cwe="CWE-79",
                    ))
                    break
        return findings

    def _check_path_traversal(self, source: str, file: str) -> list[VulnFinding]:
        findings: list[VulnFinding] = []
        patterns = [
            re.compile(r"""open\s*\(\s*(?:f['\"]|.*\+|.*\.format\(|.*%\s)"""),
            re.compile(r"""os\.path\.join\s*\(.*request"""),
            re.compile(r"""\.\./"""),
        ]
        for i, line in enumerate(source.splitlines(), 1):
            for pat in patterns:
                if pat.search(line):
                    findings.append(VulnFinding(
                        rule="path-traversal",
                        file=file,
                        line=i,
                        severity=Severity.HIGH,
                        description="Possible path traversal vulnerability",
                        fix_suggestion="Validate and canonicalize file paths; reject '..' sequences",
                        cwe="CWE-22",
                    ))
                    break
        return findings

    def _check_hardcoded_secrets(self, source: str, file: str) -> list[VulnFinding]:
        findings: list[VulnFinding] = []
        patterns = [
            re.compile(r"""(?:password|passwd|pwd)\s*=\s*['\"][^'\"]{4,}['\"]""", re.IGNORECASE),
            re.compile(r"""(?:api_key|apikey|secret_key|SECRET)\s*=\s*['\"][^'\"]{4,}['\"]""", re.IGNORECASE),
            re.compile(r"""(?:token)\s*=\s*['\"][A-Za-z0-9_\-]{8,}['\"]""", re.IGNORECASE),
        ]
        for i, line in enumerate(source.splitlines(), 1):
            for pat in patterns:
                if pat.search(line):
                    findings.append(VulnFinding(
                        rule="hardcoded-secret",
                        file=file,
                        line=i,
                        severity=Severity.CRITICAL,
                        description="Hardcoded secret or credential detected",
                        fix_suggestion="Use environment variables or a secrets manager",
                        cwe="CWE-798",
                    ))
                    break
        return findings

    # ------------------------------------------------------------------
    # Custom rules
    # ------------------------------------------------------------------

    def add_rule(self, name: str, pattern: str, severity: Severity, description: str) -> None:
        """Register a custom regex-based detection rule."""
        self._custom_rules.append({
            "name": name,
            "pattern": re.compile(pattern),
            "severity": severity,
            "description": description,
        })

    def _check_custom_rules(self, source: str, file: str) -> list[VulnFinding]:
        findings: list[VulnFinding] = []
        for rule in self._custom_rules:
            pat: re.Pattern[str] = rule["pattern"]  # type: ignore[assignment]
            for i, line in enumerate(source.splitlines(), 1):
                if pat.search(line):
                    findings.append(VulnFinding(
                        rule=rule["name"],  # type: ignore[arg-type]
                        file=file,
                        line=i,
                        severity=rule["severity"],  # type: ignore[arg-type]
                        description=rule["description"],  # type: ignore[arg-type]
                    ))
        return findings

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self, findings: list[VulnFinding]) -> str:
        """Return a human-readable summary of *findings*."""
        if not findings:
            return "No vulnerabilities found."
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
        lines = [f"Total findings: {len(findings)}"]
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            if sev in counts:
                lines.append(f"  {sev}: {counts[sev]}")
        return "\n".join(lines)
