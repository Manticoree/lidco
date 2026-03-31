"""Security pattern scanner — detect common vulnerability patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SecurityFinding:
    """A single security finding."""

    rule: str
    file: str
    line: int
    message: str
    severity: str = "high"  # "critical" / "high" / "medium" / "low"
    owasp: str = ""  # OWASP category code
    cwe: str = ""  # CWE identifier


@dataclass
class SecurityReport:
    """Aggregated security scan result."""

    findings: list[SecurityFinding] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "high")

    @property
    def total(self) -> int:
        return len(self.findings)

    def format(self) -> str:
        if not self.findings:
            return "No security issues found."
        lines = [f"Found {self.total} security issue(s):"]
        for f in self.findings:
            loc = f"{f.file}:{f.line}" if f.file else f"line {f.line}"
            owasp_tag = f" [{f.owasp}]" if f.owasp else ""
            cwe_tag = f" (CWE-{f.cwe})" if f.cwe else ""
            lines.append(
                f"  [{f.severity.upper()}]{owasp_tag}{cwe_tag} {loc} — {f.rule}: {f.message}"
            )
        return "\n".join(lines)


# Built-in security patterns --------------------------------------------------

_SECURITY_RULES: list[dict[str, Any]] = [
    {
        "name": "hardcoded_secret",
        "pattern": r"""(?:password|secret|api_?key|token|auth)\s*=\s*["'][^"']{8,}["']""",
        "message": "Possible hardcoded secret",
        "severity": "critical",
        "owasp": "A02:2021",
        "cwe": "798",
    },
    {
        "name": "sql_concat",
        "pattern": r"""(?:execute|cursor\.execute|query)\s*\(\s*(?:f["']|["'].*%s|["'].*\+)""",
        "message": "SQL string concatenation/formatting — use parameterized queries",
        "severity": "critical",
        "owasp": "A03:2021",
        "cwe": "89",
    },
    {
        "name": "eval_usage",
        "pattern": r"\beval\s*\(",
        "message": "eval() usage — potential code injection",
        "severity": "high",
        "owasp": "A03:2021",
        "cwe": "95",
    },
    {
        "name": "exec_usage",
        "pattern": r"\bexec\s*\(",
        "message": "exec() usage — potential code injection",
        "severity": "high",
        "owasp": "A03:2021",
        "cwe": "95",
    },
    {
        "name": "pickle_load",
        "pattern": r"pickle\.loads?\s*\(",
        "message": "pickle.load() — unsafe deserialization",
        "severity": "high",
        "owasp": "A08:2021",
        "cwe": "502",
    },
    {
        "name": "yaml_unsafe_load",
        "pattern": r"yaml\.load\s*\([^)]*(?!Loader)",
        "message": "yaml.load() without safe Loader — use yaml.safe_load()",
        "severity": "high",
        "owasp": "A08:2021",
        "cwe": "502",
    },
    {
        "name": "shell_injection",
        "pattern": r"(?:os\.system|subprocess\.call|subprocess\.run|subprocess\.Popen)\s*\(\s*(?:f[\"']|\w+\s*\+)",
        "message": "Shell command with string interpolation — potential command injection",
        "severity": "critical",
        "owasp": "A03:2021",
        "cwe": "78",
    },
    {
        "name": "weak_hash",
        "pattern": r"(?:hashlib\.md5|hashlib\.sha1)\s*\(",
        "message": "Weak hash algorithm (MD5/SHA1)",
        "severity": "medium",
        "owasp": "A02:2021",
        "cwe": "328",
    },
    {
        "name": "debug_mode",
        "pattern": r"""(?:DEBUG\s*=\s*True|app\.run\s*\([^)]*debug\s*=\s*True)""",
        "message": "Debug mode enabled — disable in production",
        "severity": "medium",
        "owasp": "A05:2021",
        "cwe": "489",
    },
    {
        "name": "cors_wildcard",
        "pattern": r"""(?:CORS|cors|Access-Control-Allow-Origin)\s*[:=]\s*["']\*["']""",
        "message": "CORS wildcard origin — restrict to specific domains",
        "severity": "medium",
        "owasp": "A01:2021",
        "cwe": "942",
    },
    {
        "name": "temp_file_insecure",
        "pattern": r"(?:open\s*\(\s*['\"/]tmp/|tempfile\.mktemp\s*\()",
        "message": "Insecure temp file — use tempfile.mkstemp() or NamedTemporaryFile",
        "severity": "low",
        "owasp": "A01:2021",
        "cwe": "377",
    },
    {
        "name": "assert_in_production",
        "pattern": r"^\s*assert\s+",
        "message": "Assert statement may be stripped with -O flag",
        "severity": "low",
        "owasp": "A04:2021",
        "cwe": "617",
    },
]


class SecurityPatternScanner:
    """Scan source code for security vulnerability patterns."""

    def __init__(self, rules: list[dict[str, Any]] | None = None) -> None:
        self._rules = rules if rules is not None else list(_SECURITY_RULES)

    @property
    def rules(self) -> list[dict[str, Any]]:
        return list(self._rules)

    def add_rule(self, rule: dict[str, Any]) -> None:
        self._rules = [*self._rules, rule]

    def scan(self, source: str, filename: str = "") -> SecurityReport:
        """Scan *source* for security issues."""
        findings: list[SecurityFinding] = []

        for rule in self._rules:
            pattern_str = rule.get("pattern", "")
            if not pattern_str:
                continue
            try:
                pat = re.compile(pattern_str, re.MULTILINE)
            except re.error:
                continue

            for match in pat.finditer(source):
                line_no = source[:match.start()].count("\n") + 1
                findings.append(
                    SecurityFinding(
                        rule=rule.get("name", "unknown"),
                        file=filename,
                        line=line_no,
                        message=rule.get("message", ""),
                        severity=rule.get("severity", "high"),
                        owasp=rule.get("owasp", ""),
                        cwe=rule.get("cwe", ""),
                    )
                )

        return SecurityReport(findings=findings)

    def scan_diff(self, diff_text: str) -> SecurityReport:
        """Scan only added lines from a unified diff."""
        findings: list[SecurityFinding] = []
        current_file = ""
        line_no = 0

        for raw_line in diff_text.splitlines():
            if raw_line.startswith("+++ b/"):
                current_file = raw_line[6:]
                continue
            if raw_line.startswith("@@ "):
                m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", raw_line)
                if m:
                    line_no = int(m.group(1)) - 1
                continue
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                line_no += 1
                code = raw_line[1:]
                for rule in self._rules:
                    pattern_str = rule.get("pattern", "")
                    if not pattern_str:
                        continue
                    try:
                        if re.search(pattern_str, code):
                            findings.append(
                                SecurityFinding(
                                    rule=rule.get("name", "unknown"),
                                    file=current_file,
                                    line=line_no,
                                    message=rule.get("message", ""),
                                    severity=rule.get("severity", "high"),
                                    owasp=rule.get("owasp", ""),
                                    cwe=rule.get("cwe", ""),
                                )
                            )
                    except re.error:
                        continue
            elif not raw_line.startswith("-"):
                line_no += 1

        return SecurityReport(findings=findings)
