"""SecurityGate — mandatory security scan before PR creation."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SecurityFinding:
    file: str
    line: int
    severity: str  # critical | high | medium | info
    description: str


@dataclass
class GateResult:
    passed: bool
    findings: list[SecurityFinding]
    blocked_reason: str | None = None


_SECRET_PATTERNS = [
    (re.compile(r'(?:api[_-]?key|apikey|secret[_-]?key)\s*=\s*["\'][A-Za-z0-9_\-]{16,}["\']', re.I), "hardcoded API key"),
    (re.compile(r'password\s*=\s*["\'][^"\']{4,}["\']', re.I), "hardcoded password"),
    (re.compile(r'(?:aws_access_key_id|aws_secret)\s*=\s*["\'][A-Za-z0-9/+=]{16,}["\']', re.I), "hardcoded AWS credential"),
    (re.compile(r'(?:sk-|pk-)[A-Za-z0-9]{20,}'), "potential OpenAI/Stripe key"),
]

_UNSAFE_PATTERNS = [
    (re.compile(r'eval\s*\(\s*(?:request|input|user|data)', re.I), "eval with user input"),
    (re.compile(r'subprocess\..*shell\s*=\s*True.*\+', re.I), "shell=True with string concat"),
    (re.compile(r'execute\s*\(\s*["\'].*%s.*["\']', re.I), "SQL string formatting"),
    (re.compile(r'cursor\.execute\s*\(\s*f["\']', re.I), "SQL f-string injection"),
]


class SecurityGate:
    """Run security checks before PR creation."""

    def __init__(self, project_dir: Path | None = None) -> None:
        self._project_dir = project_dir or Path.cwd()

    def check(self, changed_files: list[str], project_dir: Path | None = None) -> GateResult:
        base = project_dir or self._project_dir
        findings: list[SecurityFinding] = []

        for rel_path in changed_files:
            abs_path = base / rel_path
            if not abs_path.is_file():
                continue
            try:
                lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue

            for i, line in enumerate(lines, 1):
                for pat, desc in _SECRET_PATTERNS:
                    if pat.search(line):
                        findings.append(SecurityFinding(file=rel_path, line=i, severity="critical", description=desc))

                for pat, desc in _UNSAFE_PATTERNS:
                    if pat.search(line):
                        findings.append(SecurityFinding(file=rel_path, line=i, severity="high", description=desc))

        critical = [f for f in findings if f.severity == "critical"]
        passed = len(critical) == 0
        blocked_reason = f"{len(critical)} critical security issue(s) found" if not passed else None

        return GateResult(passed=passed, findings=findings, blocked_reason=blocked_reason)
