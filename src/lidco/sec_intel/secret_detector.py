"""Regex + entropy secret detection."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import List


@dataclass(frozen=True)
class SecretFinding:
    """A detected secret in source code."""

    file: str
    line: int
    pattern_name: str
    matched_text: str
    entropy: float = 0.0
    false_positive_likelihood: str = "low"


class SecretDetector:
    """Detect secrets in source code via regex patterns and Shannon entropy."""

    _BUILTIN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
        ("github-token", re.compile(r"gh[ps]_[A-Za-z0-9_]{36,}")),
        ("generic-api-key", re.compile(r"""(?:api_key|apikey|api-key)\s*[:=]\s*['\"]([^'\"]{8,})['\"]""", re.IGNORECASE)),
        ("generic-secret", re.compile(r"""(?:secret|secret_key)\s*[:=]\s*['\"]([^'\"]{8,})['\"]""", re.IGNORECASE)),
        ("password-assignment", re.compile(r"""(?:password|passwd|pwd)\s*[:=]\s*['\"]([^'\"]{4,})['\"]""", re.IGNORECASE)),
        ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----")),
        ("jwt-token", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ]

    def __init__(self) -> None:
        self._custom_patterns: list[tuple[str, re.Pattern[str]]] = []

    def scan(self, source: str, file: str = "") -> list[SecretFinding]:
        """Scan *source* for secrets using patterns and entropy."""
        findings: list[SecretFinding] = []
        findings.extend(self._check_patterns(source, file))
        findings.extend(self._high_entropy_strings(source, file))
        return findings

    def _check_patterns(self, source: str, file: str) -> list[SecretFinding]:
        """Check all built-in and custom regex patterns."""
        findings: list[SecretFinding] = []
        all_patterns = self._BUILTIN_PATTERNS + self._custom_patterns
        for i, line in enumerate(source.splitlines(), 1):
            for name, pat in all_patterns:
                m = pat.search(line)
                if m:
                    matched = m.group(1) if m.lastindex else m.group(0)
                    entropy = self._calculate_entropy(matched)
                    fp = "high" if entropy < 2.0 else ("medium" if entropy < 3.5 else "low")
                    findings.append(SecretFinding(
                        file=file,
                        line=i,
                        pattern_name=name,
                        matched_text=matched,
                        entropy=entropy,
                        false_positive_likelihood=fp,
                    ))
        return findings

    @staticmethod
    def _calculate_entropy(text: str) -> float:
        """Calculate Shannon entropy of *text*."""
        if not text:
            return 0.0
        length = len(text)
        freq: dict[str, int] = {}
        for ch in text:
            freq[ch] = freq.get(ch, 0) + 1
        entropy = 0.0
        for count in freq.values():
            p = count / length
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    def _high_entropy_strings(self, source: str, file: str, threshold: float = 4.5) -> list[SecretFinding]:
        """Find strings with high Shannon entropy that might be secrets."""
        findings: list[SecretFinding] = []
        # Match quoted strings of length >= 16
        pat = re.compile(r"""['\"]([A-Za-z0-9+/=_\-]{16,})['\"]""")
        for i, line in enumerate(source.splitlines(), 1):
            for m in pat.finditer(line):
                candidate = m.group(1)
                entropy = self._calculate_entropy(candidate)
                if entropy >= threshold:
                    findings.append(SecretFinding(
                        file=file,
                        line=i,
                        pattern_name="high-entropy-string",
                        matched_text=candidate,
                        entropy=entropy,
                        false_positive_likelihood="medium",
                    ))
        return findings

    def add_pattern(self, name: str, regex: str) -> None:
        """Register a custom detection pattern."""
        self._custom_patterns.append((name, re.compile(regex)))

    @staticmethod
    def is_ignored(path: str, gitignore_patterns: list[str] | None = None) -> bool:
        """Check if *path* matches any gitignore-style patterns."""
        if gitignore_patterns is None:
            return False
        for pattern in gitignore_patterns:
            if fnmatch(path, pattern):
                return True
        return False

    def summary(self, findings: list[SecretFinding]) -> str:
        """Return a human-readable summary of *findings*."""
        if not findings:
            return "No secrets detected."
        by_pattern: dict[str, int] = {}
        for f in findings:
            by_pattern[f.pattern_name] = by_pattern.get(f.pattern_name, 0) + 1
        lines = [f"Secrets detected: {len(findings)}"]
        for name, count in sorted(by_pattern.items()):
            lines.append(f"  {name}: {count}")
        return "\n".join(lines)
