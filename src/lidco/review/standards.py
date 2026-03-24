"""StandardsEnforcer — check code against configurable style/quality rules."""
from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


@dataclass
class StandardRule:
    id: str
    name: str
    description: str
    pattern: str
    severity: str  # "error" | "warning" | "info"
    file_glob: str  # e.g. "*.py"
    fix_hint: str = ""


@dataclass
class Violation:
    rule_id: str
    file: str
    line: int
    message: str
    severity: str
    fix_hint: str


@dataclass
class CheckResult:
    passed: bool
    violations: list[Violation]
    rules_checked: int


class StandardsEnforcer:
    """Check files or diffs against a list of StandardRule objects."""

    def __init__(self, rules_path: Path | str | None = None) -> None:
        self._rules: list[StandardRule] = []
        if rules_path:
            self.load_rules(rules_path)

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def load_rules(self, path: Path | str) -> list[StandardRule]:
        """Load rules from a YAML (or JSON fallback) file."""
        text = Path(path).read_text(encoding="utf-8")
        data = None

        if yaml is not None:
            try:
                data = yaml.safe_load(text)
            except Exception:
                data = None

        if data is None:
            data = json.loads(text)

        loaded: list[StandardRule] = []
        for entry in data:
            rule = StandardRule(
                id=entry["id"],
                name=entry["name"],
                description=entry.get("description", ""),
                pattern=entry["pattern"],
                severity=entry.get("severity", "warning"),
                file_glob=entry.get("file_glob", "*"),
                fix_hint=entry.get("fix_hint", ""),
            )
            loaded.append(rule)

        self._rules = [*self._rules, *loaded]
        return loaded

    def add_rule(self, rule: StandardRule) -> None:
        """Append a rule (immutable list replacement)."""
        self._rules = [*self._rules, rule]

    def rules(self) -> list[StandardRule]:
        """Return a copy of the rules list."""
        return list(self._rules)

    # ------------------------------------------------------------------
    # Checking
    # ------------------------------------------------------------------

    def check_file(self, file_path: str, content: str) -> list[Violation]:
        """Check content of a single file against applicable rules."""
        violations: list[Violation] = []
        lines = content.splitlines()

        for rule in self._rules:
            if not fnmatch.fnmatch(Path(file_path).name, rule.file_glob):
                continue

            try:
                pat = re.compile(rule.pattern)
            except re.error:
                continue

            for lineno, line in enumerate(lines, 1):
                if pat.search(line):
                    violations.append(Violation(
                        rule_id=rule.id,
                        file=file_path,
                        line=lineno,
                        message=f"[{rule.id}] {rule.name}: {line.strip()[:120]}",
                        severity=rule.severity,
                        fix_hint=rule.fix_hint,
                    ))

        return violations

    def check_diff(self, changed_files: dict[str, str]) -> CheckResult:
        """Check a dict of {path: content} files.

        passed=True when there are no "error" violations.
        """
        all_violations: list[Violation] = []
        for path, content in changed_files.items():
            all_violations.extend(self.check_file(path, content))

        has_error = any(v.severity == "error" for v in all_violations)
        return CheckResult(
            passed=not has_error,
            violations=all_violations,
            rules_checked=len(self._rules),
        )

    # ------------------------------------------------------------------
    # Built-in rules
    # ------------------------------------------------------------------

    @staticmethod
    def default_rules() -> list[StandardRule]:
        """Return 5 built-in rules."""
        return [
            StandardRule(
                id="PY001",
                name="no-print",
                description="Avoid print() in production code",
                pattern=r"\bprint\s*\(",
                severity="warning",
                file_glob="*.py",
                fix_hint="Use logging instead of print().",
            ),
            StandardRule(
                id="PY002",
                name="todo-without-owner",
                description="TODO must have an owner: TODO(name):",
                pattern=r"#\s*TODO(?!\s*\()",
                severity="info",
                file_glob="*.py",
                fix_hint="Add owner: # TODO(yourname): description",
            ),
            StandardRule(
                id="GEN001",
                name="no-hardcoded-localhost",
                description="No hardcoded localhost:<port> in source",
                pattern=r"localhost:\d+",
                severity="warning",
                file_glob="*",
                fix_hint="Use configuration variables for hostnames.",
            ),
            StandardRule(
                id="GEN002",
                name="max-line-length-120",
                description="Lines must not exceed 120 characters",
                pattern=r".{121,}",
                severity="info",
                file_glob="*",
                fix_hint="Break long lines to <= 120 characters.",
            ),
            StandardRule(
                id="PY003",
                name="type-ignore-without-reason",
                description="# type: ignore must include a reason in brackets",
                pattern=r"#\s*type:\s*ignore\s*$",
                severity="warning",
                file_glob="*.py",
                fix_hint="Add reason: # type: ignore[assignment]",
            ),
        ]
