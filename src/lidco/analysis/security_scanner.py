"""Security pattern scanner (AST-based) — Task 348."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum


class SecuritySeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class SecurityFinding:
    rule_id: str
    title: str
    severity: SecuritySeverity
    file: str
    line: int
    detail: str


# ---------------------------------------------------------------------------
# Rule catalogue
# ---------------------------------------------------------------------------

# Dangerous function calls (name → (rule_id, title, severity))
_DANGEROUS_CALLS: dict[str, tuple[str, str, SecuritySeverity]] = {
    "eval": ("SEC001", "Use of eval()", SecuritySeverity.CRITICAL),
    "exec": ("SEC002", "Use of exec()", SecuritySeverity.CRITICAL),
    "compile": ("SEC003", "Dynamic code compilation via compile()", SecuritySeverity.HIGH),
    "pickle.loads": ("SEC004", "Unsafe deserialization via pickle.loads", SecuritySeverity.HIGH),
    "pickle.load": ("SEC004", "Unsafe deserialization via pickle.load", SecuritySeverity.HIGH),
    "marshal.loads": ("SEC005", "Unsafe deserialization via marshal.loads", SecuritySeverity.HIGH),
    "yaml.load": ("SEC006", "Unsafe YAML load (use yaml.safe_load)", SecuritySeverity.HIGH),
    "subprocess.call": ("SEC007", "subprocess.call usage", SecuritySeverity.MEDIUM),
    "subprocess.run": ("SEC007", "subprocess.run usage", SecuritySeverity.LOW),
    "os.system": ("SEC008", "Use of os.system", SecuritySeverity.HIGH),
    "os.popen": ("SEC008", "Use of os.popen", SecuritySeverity.HIGH),
    "tempfile.mktemp": ("SEC009", "Insecure temp file creation (use mkstemp)", SecuritySeverity.MEDIUM),
    "hashlib.md5": ("SEC010", "Weak hash algorithm MD5", SecuritySeverity.MEDIUM),
    "hashlib.sha1": ("SEC010", "Weak hash algorithm SHA1", SecuritySeverity.LOW),
}

# Assert statement (stripped in -O mode)
_ASSERT_RULE = ("SEC011", "Assert used for security check (stripped in -O mode)", SecuritySeverity.MEDIUM)


def _call_name(node: ast.Call) -> str:
    """Extract the dotted name of a call node, e.g. 'yaml.load'."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name):
            return f"{func.value.id}.{func.attr}"
    return ""


class SecurityScanner:
    """AST-based security pattern scanner."""

    def scan(self, source: str, file_path: str = "") -> list[SecurityFinding]:
        """Return security findings for *source*."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        findings: list[SecurityFinding] = []

        for node in ast.walk(tree):
            # Dangerous function calls
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name in _DANGEROUS_CALLS:
                    rule_id, title, severity = _DANGEROUS_CALLS[name]
                    findings.append(
                        SecurityFinding(
                            rule_id=rule_id,
                            title=title,
                            severity=severity,
                            file=file_path,
                            line=node.lineno,
                            detail=f"Call to {name}() detected",
                        )
                    )

            # Assert used for security (simplified: any assert in a function
            # whose name suggests authentication/authorization/permission)
            elif isinstance(node, ast.Assert):
                findings.append(
                    SecurityFinding(
                        rule_id=_ASSERT_RULE[0],
                        title=_ASSERT_RULE[1],
                        severity=_ASSERT_RULE[2],
                        file=file_path,
                        line=node.lineno,
                        detail="assert statement found (optimized away with -O)",
                    )
                )

        return findings

    def filter_by_severity(
        self, findings: list[SecurityFinding], min_severity: SecuritySeverity
    ) -> list[SecurityFinding]:
        """Return findings at or above *min_severity*."""
        _ORDER = [
            SecuritySeverity.LOW,
            SecuritySeverity.MEDIUM,
            SecuritySeverity.HIGH,
            SecuritySeverity.CRITICAL,
        ]
        min_idx = _ORDER.index(min_severity)
        return [f for f in findings if _ORDER.index(f.severity) >= min_idx]
