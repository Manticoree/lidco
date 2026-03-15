"""Secret detection for pre-commit hooks — Task 324.

Scans files and diffs for common secrets patterns: API keys, passwords,
tokens, connection strings, private keys, etc.

Usage::

    detector = SecretDetector()
    findings = detector.scan_file("config.py")
    for f in findings:
        print(f.rule_id, f.line_number, f.redacted)

    findings = detector.scan_text(diff_content)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Pattern


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

@dataclass
class SecretRule:
    rule_id: str
    pattern: Pattern
    description: str
    severity: str = "HIGH"   # HIGH | MEDIUM | LOW


_RULES: list[SecretRule] = [
    SecretRule(
        "generic-api-key",
        re.compile(r'(?i)(api[_\-]?key|apikey)\s*[:=]\s*["\']?([A-Za-z0-9\-_]{20,})["\']?'),
        "Generic API key",
    ),
    SecretRule(
        "aws-access-key",
        re.compile(r'AKIA[0-9A-Z]{16}'),
        "AWS access key ID",
    ),
    SecretRule(
        "aws-secret-key",
        re.compile(r'(?i)aws[_\-]?secret[_\-]?access[_\-]?key\s*[:=]\s*["\']?([A-Za-z0-9/+=]{40})["\']?'),
        "AWS secret access key",
    ),
    SecretRule(
        "github-token",
        re.compile(r'(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}'),
        "GitHub personal access token",
    ),
    SecretRule(
        "openai-key",
        re.compile(r'sk-[A-Za-z0-9]{20,}'),
        "OpenAI / Anthropic API key",
    ),
    SecretRule(
        "private-key-header",
        re.compile(r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'),
        "Private key material",
    ),
    SecretRule(
        "password-assignment",
        re.compile(r'(?i)(password|passwd|pwd)\s*[:=]\s*["\'](?!.*\{)[^"\']{8,}["\']'),
        "Hardcoded password",
        severity="HIGH",
    ),
    SecretRule(
        "connection-string",
        re.compile(r'(?i)(mysql|postgresql|postgres|mongodb)://[^@\s]+:[^@\s]+@'),
        "Database connection string with credentials",
    ),
    SecretRule(
        "jwt-token",
        re.compile(r'eyJ[A-Za-z0-9\-_=]+\.eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_.+/=]+'),
        "JWT token",
        severity="MEDIUM",
    ),
    SecretRule(
        "generic-secret",
        re.compile(r'(?i)(secret|token|auth)[_\-]?(?:key)?\s*[:=]\s*["\']([A-Za-z0-9\-_/+=]{16,})["\']'),
        "Generic secret value",
        severity="MEDIUM",
    ),
]


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

@dataclass
class SecretFinding:
    """A detected secret in source code."""

    rule_id: str
    description: str
    severity: str
    line_number: int
    line: str
    file_path: str = ""

    @property
    def redacted(self) -> str:
        """Return the line with the matched secret partially redacted."""
        # Replace sequences of 8+ alphanumeric chars (likely secrets) with ***
        return re.sub(r'[A-Za-z0-9]{8,}', lambda m: m.group()[:4] + "****", self.line)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class SecretDetector:
    """Scans text or files for secrets using regex rules.

    Args:
        rules: Custom rules list. Defaults to built-in rules.
        skip_extensions: File extensions to skip (e.g. compiled files).
    """

    _DEFAULT_SKIP = {".pyc", ".class", ".exe", ".bin", ".lock"}

    def __init__(
        self,
        rules: list[SecretRule] | None = None,
        skip_extensions: set[str] | None = None,
    ) -> None:
        self._rules = rules if rules is not None else _RULES
        self._skip = skip_extensions if skip_extensions is not None else self._DEFAULT_SKIP

    def scan_text(
        self,
        text: str,
        file_path: str = "",
        ignore_lines: set[int] | None = None,
    ) -> list[SecretFinding]:
        """Scan a string for secrets. Returns list of findings."""
        findings: list[SecretFinding] = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            if ignore_lines and line_no in ignore_lines:
                continue
            # Skip comment-only "example" lines
            stripped = line.strip()
            if stripped.startswith("#") or "example" in stripped.lower():
                continue
            for rule in self._rules:
                if rule.pattern.search(line):
                    findings.append(
                        SecretFinding(
                            rule_id=rule.rule_id,
                            description=rule.description,
                            severity=rule.severity,
                            line_number=line_no,
                            line=line.rstrip(),
                            file_path=file_path,
                        )
                    )
                    break  # one finding per line per rule match
        return findings

    def scan_file(self, path: str | Path) -> list[SecretFinding]:
        """Scan a file for secrets."""
        p = Path(path)
        if p.suffix in self._skip:
            return []
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return self.scan_text(text, file_path=str(p))

    def scan_diff(self, diff_text: str) -> list[SecretFinding]:
        """Scan a git diff (only added lines, i.e. lines starting with '+')."""
        added_lines: list[str] = []
        for line in diff_text.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])  # strip the leading '+'
        return self.scan_text("\n".join(added_lines), file_path="<diff>")

    def scan_files(self, paths: list[str | Path]) -> list[SecretFinding]:
        """Scan multiple files and return all findings."""
        results: list[SecretFinding] = []
        for p in paths:
            results.extend(self.scan_file(p))
        return results
