"""SecretScanner — scan text/files for leaked secrets with pattern + entropy detection."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SecretFinding:
    """A single secret found during scanning."""

    type: str
    value_preview: str
    line: int
    column: int
    severity: str  # low / medium / high / critical
    confidence: float


@dataclass(frozen=True)
class ScanResult:
    """Aggregated result of a scan."""

    findings: list[SecretFinding]
    scanned_lines: int
    file_path: str = ""


# Default built-in patterns: (name -> (regex, severity))
_BUILTIN_PATTERNS: dict[str, tuple[str, str]] = {
    "aws_access_key": (r"AKIA[0-9A-Z]{16}", "critical"),
    "aws_secret_key": (r"(?i)aws[_\-]?secret[_\-]?access[_\-]?key\s*[=:]\s*\S{20,}", "critical"),
    "github_pat": (r"ghp_[0-9a-zA-Z]{36}", "critical"),
    "github_oauth": (r"gho_[0-9a-zA-Z]{36}", "critical"),
    "github_app": (r"ghs_[0-9a-zA-Z]{36}", "critical"),
    "github_fine_grained": (r"github_pat_[0-9a-zA-Z_]{22,}", "critical"),
    "generic_api_key": (r"(?i)api[_\-]?key\s*[=:]\s*['\"]?\S{16,}['\"]?", "high"),
    "generic_api_secret": (r"(?i)api[_\-]?secret\s*[=:]\s*['\"]?\S{16,}['\"]?", "high"),
    "generic_token": (r"(?i)token\s*[=:]\s*['\"]?\S{20,}['\"]?", "medium"),
    "password_assignment": (r"(?i)password\s*[=:]\s*['\"]?\S{6,}['\"]?", "high"),
    "passwd_assignment": (r"(?i)passwd\s*[=:]\s*['\"]?\S{6,}['\"]?", "high"),
    "private_key_rsa": (r"-----BEGIN RSA PRIVATE KEY-----", "critical"),
    "private_key_ec": (r"-----BEGIN EC PRIVATE KEY-----", "critical"),
    "private_key_openssh": (r"-----BEGIN OPENSSH PRIVATE KEY-----", "critical"),
    "private_key_generic": (r"-----BEGIN PRIVATE KEY-----", "critical"),
    "jwt_token": (r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "high"),
    "slack_token": (r"xox[bporas]-[0-9a-zA-Z\-]{10,}", "critical"),
    "slack_webhook": (r"https://hooks\.slack\.com/services/T[0-9A-Z]{8,}/B[0-9A-Z]{8,}/[0-9a-zA-Z]{20,}", "high"),
    "basic_auth_url": (r"https?://[^:]+:[^@]+@[^\s]+", "high"),
    "env_secret": (r"(?i)(?:SECRET|TOKEN|PASSWORD|PASSWD|API_KEY)\s*=\s*\S{6,}", "high"),
    "env_private_key": (r"(?i)PRIVATE[_\-]?KEY\s*=\s*\S{10,}", "critical"),
    "heroku_api_key": (r"(?i)heroku[_\-]?api[_\-]?key\s*[=:]\s*\S{20,}", "high"),
    "sendgrid_api_key": (r"SG\.[0-9a-zA-Z_\-]{22}\.[0-9a-zA-Z_\-]{43}", "critical"),
    "twilio_api_key": (r"SK[0-9a-f]{32}", "high"),
    "stripe_secret": (r"sk_live_[0-9a-zA-Z]{24,}", "critical"),
    "stripe_publishable": (r"pk_live_[0-9a-zA-Z]{24,}", "medium"),
    "google_api_key": (r"AIza[0-9A-Za-z\-_]{35}", "high"),
    "mailgun_api_key": (r"key-[0-9a-zA-Z]{32}", "high"),
    "npm_token": (r"npm_[0-9a-zA-Z]{36}", "critical"),
    "pypi_token": (r"pypi-[0-9a-zA-Z_\-]{50,}", "critical"),
    "bearer_token": (r"(?i)bearer\s+[0-9a-zA-Z_\-\.]{20,}", "high"),
    "connection_string": (r"(?i)(?:mongodb|postgres|mysql|redis)://\S+:\S+@\S+", "critical"),
}


class SecretScanner:
    """Scan text for secrets using regex patterns and Shannon entropy."""

    def __init__(
        self,
        custom_patterns: dict[str, str] | None = None,
        entropy_threshold: float = 4.0,
    ) -> None:
        self._patterns: dict[str, tuple[re.Pattern[str], str]] = {}
        for name, (regex, severity) in _BUILTIN_PATTERNS.items():
            self._patterns[name] = (re.compile(regex), severity)
        if custom_patterns:
            for name, regex in custom_patterns.items():
                self._patterns[name] = (re.compile(regex), "high")
        self._entropy_threshold = entropy_threshold
        self._total_scans = 0
        self._total_findings = 0

    # -- public API --

    def scan_text(self, text: str, source: str = "") -> ScanResult:
        """Scan a block of text and return findings."""
        lines = text.splitlines()
        return self.scan_lines(lines, source)

    def scan_lines(self, lines: list[str], source: str = "") -> ScanResult:
        """Scan a list of lines and return findings."""
        findings: list[SecretFinding] = []
        for idx, line in enumerate(lines):
            line_num = idx + 1
            # Pattern-based detection
            for name, (pattern, severity) in self._patterns.items():
                for m in pattern.finditer(line):
                    val = m.group(0)
                    preview = val[:8] + "..." if len(val) > 8 else val
                    findings.append(SecretFinding(
                        type=name,
                        value_preview=preview,
                        line=line_num,
                        column=m.start() + 1,
                        severity=severity,
                        confidence=0.9,
                    ))
            # Entropy-based detection
            findings.extend(self._check_entropy(line, line_num))
        self._total_scans += 1
        self._total_findings += len(findings)
        return ScanResult(findings=findings, scanned_lines=len(lines), file_path=source)

    def add_pattern(self, name: str, regex: str, severity: str = "high") -> None:
        """Register a custom detection pattern."""
        self._patterns[name] = (re.compile(regex), severity)

    @property
    def patterns(self) -> dict[str, str]:
        """Return pattern names mapped to their regex strings."""
        return {name: pat.pattern for name, (pat, _sev) in self._patterns.items()}

    def summary(self) -> dict:
        """Return scanner statistics."""
        return {
            "pattern_count": len(self._patterns),
            "entropy_threshold": self._entropy_threshold,
            "total_scans": self._total_scans,
            "total_findings": self._total_findings,
        }

    # -- private --

    def _calculate_entropy(self, s: str) -> float:
        """Compute Shannon entropy of string *s*."""
        if not s:
            return 0.0
        freq: dict[str, int] = {}
        for ch in s:
            freq[ch] = freq.get(ch, 0) + 1
        length = len(s)
        entropy = 0.0
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)
        return entropy

    def _check_entropy(self, line: str, line_num: int) -> list[SecretFinding]:
        """Find high-entropy hex/base64 tokens in a line."""
        findings: list[SecretFinding] = []
        # Match hex or base64-ish tokens of 20+ chars
        for m in re.finditer(r"[0-9a-fA-F]{20,}|[A-Za-z0-9+/=_\-]{20,}", line):
            token = m.group(0)
            if len(token) < 20:
                continue
            ent = self._calculate_entropy(token)
            if ent > self._entropy_threshold:
                preview = token[:8] + "..."
                findings.append(SecretFinding(
                    type="high_entropy_string",
                    value_preview=preview,
                    line=line_num,
                    column=m.start() + 1,
                    severity="medium",
                    confidence=round(min(ent / 6.0, 1.0), 2),
                ))
        return findings
