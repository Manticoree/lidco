"""BugBotPRTrigger — scan PR diffs for bugs and code smells (Task 697)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BugSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_SEVERITY_ORDER = {
    BugSeverity.CRITICAL: 0,
    BugSeverity.HIGH: 1,
    BugSeverity.MEDIUM: 2,
    BugSeverity.LOW: 3,
}


@dataclass
class BugBotFinding:
    file: str
    line: int
    severity: BugSeverity
    message: str
    rule_id: str
    suggested_fix: Optional[str] = None


@dataclass
class PREvent:
    pr_number: int
    repo: str
    diff: str
    branch: str = "main"


class BugBotPRTrigger:
    """Scan PR diffs for bug patterns and produce findings."""

    def __init__(self, bugbot_analyzer=None, pr_reviewer=None):
        self._bugbot_analyzer = bugbot_analyzer
        self._pr_reviewer = pr_reviewer

    def process_pr_event(self, event: PREvent) -> list[BugBotFinding]:
        """Process a PR event and return deduplicated, severity-sorted findings."""
        findings: list[BugBotFinding] = []

        changed = self.parse_diff(event.diff)

        # Use injected analyzers if available
        if self._bugbot_analyzer is not None:
            for filename, lines in changed.items():
                source = "\n".join(lines)
                try:
                    reports = self._bugbot_analyzer.analyze(source, filename)
                    for r in reports:
                        sev = self._map_severity(r.severity)
                        findings.append(BugBotFinding(
                            file=r.file,
                            line=r.line,
                            severity=sev,
                            message=r.message,
                            rule_id=r.kind,
                        ))
                except Exception:
                    pass

        if self._pr_reviewer is not None:
            try:
                result = self._pr_reviewer.review(event.repo, event.pr_number)
                for c in result.comments:
                    sev = self._map_reviewer_severity(c.severity)
                    findings.append(BugBotFinding(
                        file=c.path,
                        line=c.line,
                        severity=sev,
                        message=c.body,
                        rule_id="pr_review",
                        suggested_fix=getattr(c, "suggestion", None) or None,
                    ))
            except Exception:
                pass

        # Heuristic scanning on diff text
        heuristic_findings = self._heuristic_scan(event.diff, changed)
        findings.extend(heuristic_findings)

        # Deduplicate by (file, line, rule_id)
        seen: set[tuple[str, int, str]] = set()
        unique: list[BugBotFinding] = []
        for f in findings:
            key = (f.file, f.line, f.rule_id)
            if key not in seen:
                seen.add(key)
                unique.append(f)

        # Sort by severity (CRITICAL first)
        unique.sort(key=lambda f: _SEVERITY_ORDER.get(f.severity, 99))
        return unique

    def parse_diff(self, diff: str) -> dict[str, list[str]]:
        """Parse unified diff, return {filename: [changed_lines]}."""
        result: dict[str, list[str]] = {}
        current_file: Optional[str] = None

        for raw_line in diff.splitlines():
            # Detect file header
            if raw_line.startswith("+++ b/"):
                current_file = raw_line[6:]
                if current_file not in result:
                    result[current_file] = []
            elif raw_line.startswith("+++ "):
                candidate = raw_line[4:].strip()
                if candidate and candidate != "/dev/null":
                    current_file = candidate
                    if current_file not in result:
                        result[current_file] = []
            elif raw_line.startswith("+") and not raw_line.startswith("+++"):
                if current_file is not None:
                    result[current_file].append(raw_line[1:])
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _heuristic_scan(
        self, diff: str, changed: dict[str, list[str]]
    ) -> list[BugBotFinding]:
        findings: list[BugBotFinding] = []
        for filename, lines in changed.items():
            for i, line in enumerate(lines, start=1):
                # TODO/FIXME
                if re.search(r"\bTODO\b|\bFIXME\b", line, re.IGNORECASE):
                    findings.append(BugBotFinding(
                        file=filename, line=i, severity=BugSeverity.LOW,
                        message="TODO/FIXME comment detected",
                        rule_id="todo_fixme",
                    ))
                # bare except
                if re.search(r"\bexcept\s*:", line):
                    findings.append(BugBotFinding(
                        file=filename, line=i, severity=BugSeverity.MEDIUM,
                        message="Bare `except:` catches all exceptions",
                        rule_id="bare_except",
                    ))
                # eval(
                if re.search(r"\beval\s*\(", line):
                    findings.append(BugBotFinding(
                        file=filename, line=i, severity=BugSeverity.HIGH,
                        message="Use of eval() is dangerous",
                        rule_id="eval_usage",
                    ))
                # hardcoded password/secret
                if re.search(r'(?:password|secret)\s*=\s*["\']', line, re.IGNORECASE):
                    findings.append(BugBotFinding(
                        file=filename, line=i, severity=BugSeverity.CRITICAL,
                        message="Hardcoded password or secret detected",
                        rule_id="hardcoded_secret",
                    ))
        return findings

    @staticmethod
    def _map_severity(sev: str) -> BugSeverity:
        mapping = {
            "error": BugSeverity.HIGH,
            "warning": BugSeverity.MEDIUM,
            "info": BugSeverity.LOW,
        }
        return mapping.get(sev, BugSeverity.LOW)

    @staticmethod
    def _map_reviewer_severity(sev: str) -> BugSeverity:
        mapping = {
            "critical": BugSeverity.CRITICAL,
            "warning": BugSeverity.MEDIUM,
            "suggestion": BugSeverity.LOW,
        }
        return mapping.get(sev, BugSeverity.LOW)
