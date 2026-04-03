"""DLP Scanner — detect sensitive data in outbound content."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

_BUILTIN_PATTERNS: list[tuple[str, str, str, str]] = [
    # (name, regex, type, severity)
    ("email", r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", "pii", "medium"),
    ("phone", r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "pii", "medium"),
    ("ssn", r"\b\d{3}-\d{2}-\d{4}\b", "pii", "critical"),
    ("credit_card", r"\b(?:\d[ -]*?){13,16}\b", "pii", "critical"),
    ("aws_key", r"\bAKIA[0-9A-Z]{16}\b", "credential", "critical"),
    ("sk_key", r"\bsk-[a-zA-Z0-9]{20,}\b", "credential", "critical"),
    ("password_str", r"""(?:password|passwd|pwd)\s*[:=]\s*['"][^'"]{3,}['"]""", "credential", "high"),
    ("private_key", r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----", "credential", "critical"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b", "credential", "high"),
    ("connection_string", r"(?:mysql|postgres|mongodb|redis)://[^\s]+", "credential", "high"),
]


@dataclass(frozen=True)
class DLPFinding:
    """A single sensitive-data finding."""

    type: str  # pii / credential / proprietary / sensitive
    severity: str  # low / medium / high / critical
    match: str  # masked preview
    position: int
    context: str = ""


@dataclass(frozen=True)
class DLPScanResult:
    """Result of a DLP scan."""

    findings: list[DLPFinding]
    blocked: bool
    total_scanned: int
    recommendation: str


def _mask(value: str) -> str:
    """Return a masked preview of *value*."""
    if len(value) <= 4:
        return "****"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


class DLPScanner:
    """Scan content for sensitive data patterns."""

    def __init__(self, block_threshold: str = "high") -> None:
        self._block_threshold = block_threshold
        self._patterns: dict[str, tuple[re.Pattern[str], str, str]] = {}
        self._total_scans = 0
        self._total_findings = 0
        for name, regex, typ, sev in _BUILTIN_PATTERNS:
            self._patterns[name] = (re.compile(regex, re.IGNORECASE), typ, sev)

    # ------------------------------------------------------------------

    def scan(self, content: str) -> DLPScanResult:
        """Scan *content* and return findings."""
        self._total_scans += 1
        findings: list[DLPFinding] = []
        for _name, (pat, typ, sev) in self._patterns.items():
            for m in pat.finditer(content):
                findings.append(
                    DLPFinding(
                        type=typ,
                        severity=sev,
                        match=_mask(m.group()),
                        position=m.start(),
                        context=content[max(0, m.start() - 20): m.end() + 20],
                    )
                )
        self._total_findings += len(findings)
        blocked = self.should_block_findings(findings)
        if blocked:
            rec = "Content blocked — sensitive data detected above threshold."
        elif findings:
            rec = "Review findings before sharing content."
        else:
            rec = "No sensitive data detected."
        return DLPScanResult(
            findings=findings,
            blocked=blocked,
            total_scanned=len(content),
            recommendation=rec,
        )

    def should_block(self, result: DLPScanResult) -> bool:
        """Return True if *result* warrants blocking."""
        return self.should_block_findings(result.findings)

    def should_block_findings(self, findings: list[DLPFinding]) -> bool:
        threshold = _SEVERITY_ORDER.get(self._block_threshold, 2)
        return any(_SEVERITY_ORDER.get(f.severity, 0) >= threshold for f in findings)

    def add_pattern(self, name: str, regex: str, severity: str = "high") -> None:
        """Register a custom pattern."""
        self._patterns[name] = (re.compile(regex), "sensitive", severity)

    def patterns(self) -> dict[str, str]:
        """Return {name: regex_source} for all patterns."""
        return {n: p.pattern for n, (p, _t, _s) in self._patterns.items()}

    def summary(self) -> dict:
        return {
            "total_scans": self._total_scans,
            "total_findings": self._total_findings,
            "pattern_count": len(self._patterns),
            "block_threshold": self._block_threshold,
        }
