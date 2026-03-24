"""Auto-approve rules engine — configurable gates for autonomous PR merging (Copilot/Cursor parity)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ApprovalRule:
    name: str
    description: str
    # All conditions must be True for rule to APPROVE
    max_lines_changed: int | None = None      # None = no limit
    require_tests_pass: bool = False
    blocked_patterns: list[str] = field(default_factory=list)  # regex patterns that block approval
    allowed_file_patterns: list[str] = field(default_factory=list)  # if set, only these files OK
    blocked_file_patterns: list[str] = field(default_factory=list)
    require_no_secrets: bool = True


@dataclass
class DiffStats:
    lines_added: int
    lines_removed: int
    files_changed: list[str]
    has_secrets: bool = False

    @property
    def total_lines(self) -> int:
        return self.lines_added + self.lines_removed


@dataclass
class ApprovalDecision:
    approved: bool
    rule_name: str
    reasons: list[str] = field(default_factory=list)

    def format(self) -> str:
        status = "APPROVED" if self.approved else "BLOCKED"
        lines = [f"[{status}] Rule: {self.rule_name}"]
        for r in self.reasons:
            lines.append(f"  - {r}")
        return "\n".join(lines)


# Common secret patterns
_SECRET_PATTERNS = [
    r'(?i)(api[_-]?key|secret|password|token|passwd)\s*[=:]\s*["\']?[\w\-]{8,}',
    r'(?i)sk-[a-zA-Z0-9]{20,}',
    r'(?i)Bearer\s+[a-zA-Z0-9\-_.]{20,}',
    r'(?i)AWS_SECRET',
]


def _has_secrets(diff_text: str) -> bool:
    added = "\n".join(ln[1:] for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
    return any(re.search(p, added) for p in _SECRET_PATTERNS)


def parse_diff_stats(diff_text: str) -> DiffStats:
    """Parse a unified diff and return basic stats."""
    lines_added = sum(1 for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
    lines_removed = sum(1 for ln in diff_text.splitlines() if ln.startswith("-") and not ln.startswith("---"))
    files: list[str] = []
    for ln in diff_text.splitlines():
        m = re.match(r"^\+\+\+ b/(.+)$", ln)
        if m:
            files.append(m.group(1))
    return DiffStats(
        lines_added=lines_added,
        lines_removed=lines_removed,
        files_changed=files,
        has_secrets=_has_secrets(diff_text),
    )


class ApprovalEngine:
    """Evaluate a diff against configured approval rules."""

    def __init__(self) -> None:
        self._rules: list[ApprovalRule] = []

    def add_rule(self, rule: ApprovalRule) -> None:
        self._rules.append(rule)

    def load_defaults(self) -> None:
        """Load sensible default rules."""
        self.add_rule(ApprovalRule(
            name="small-safe-change",
            description="Auto-approve small changes with no secrets",
            max_lines_changed=50,
            require_no_secrets=True,
            blocked_patterns=[r"os\.system|subprocess\.call|eval\(|exec\("],
        ))
        self.add_rule(ApprovalRule(
            name="docs-only",
            description="Auto-approve documentation-only changes",
            allowed_file_patterns=[r"\.md$", r"\.rst$", r"\.txt$", r"docs/"],
            require_no_secrets=True,
        ))

    def evaluate(self, diff_text: str, rule: ApprovalRule, tests_passed: bool = True) -> ApprovalDecision:
        """Evaluate a single rule against a diff."""
        stats = parse_diff_stats(diff_text)
        reasons: list[str] = []
        approved = True

        # Secret check
        if rule.require_no_secrets and stats.has_secrets:
            reasons.append("Secrets detected in diff")
            approved = False

        # Line limit
        if rule.max_lines_changed is not None and stats.total_lines > rule.max_lines_changed:
            reasons.append(f"Too many lines changed: {stats.total_lines} > {rule.max_lines_changed}")
            approved = False

        # Tests
        if rule.require_tests_pass and not tests_passed:
            reasons.append("Tests did not pass")
            approved = False

        # Blocked patterns in diff content (added lines only)
        added = "\n".join(ln[1:] for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
        for pat in rule.blocked_patterns:
            if re.search(pat, added):
                reasons.append(f"Blocked pattern found: {pat}")
                approved = False

        # File pattern restrictions
        if rule.allowed_file_patterns:
            if not stats.files_changed:
                reasons.append("No recognizable files changed (allowed_file_patterns requires +++ b/ headers)")
                approved = False
            else:
                bad = [f for f in stats.files_changed
                       if not any(re.search(p, f) for p in rule.allowed_file_patterns)]
                if bad:
                    reasons.append(f"Files not in allowed list: {bad[:3]}")
                    approved = False

        if rule.blocked_file_patterns:
            bad = [f for f in stats.files_changed
                   if any(re.search(p, f) for p in rule.blocked_file_patterns)]
            if bad:
                reasons.append(f"Blocked file patterns matched: {bad[:3]}")
                approved = False

        if approved:
            reasons.append("All checks passed")
        return ApprovalDecision(approved=approved, rule_name=rule.name, reasons=reasons)

    def evaluate_all(self, diff_text: str, tests_passed: bool = True) -> list[ApprovalDecision]:
        return [self.evaluate(diff_text, rule, tests_passed) for rule in self._rules]

    def is_auto_approvable(self, diff_text: str, tests_passed: bool = True) -> bool:
        """Return True if ANY rule approves the diff."""
        return any(d.approved for d in self.evaluate_all(diff_text, tests_passed))
