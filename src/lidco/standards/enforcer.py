"""StandardsEnforcer — check files against YAML-defined coding rules."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import]
except ImportError:
    yaml = None  # type: ignore[assignment]


@dataclass
class StandardsRule:
    id: str
    name: str
    pattern: str  # regex to detect violation
    message: str
    severity: str = "warning"  # "error" | "warning" | "info"
    file_glob: str = "*.py"


@dataclass
class Violation:
    rule_id: str
    rule_name: str
    file: str
    line: int
    matched_text: str
    message: str
    severity: str


DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "id": "NO_PRINT",
        "name": "No print statements",
        "pattern": r"\bprint\s*\(",
        "message": "Use logging instead of print()",
        "severity": "warning",
        "file_glob": "*.py",
    },
    {
        "id": "NO_HARDCODED_SECRET",
        "name": "No hardcoded secrets",
        "pattern": r"(password|secret|api_key)\s*=\s*['\"][^'\"]{4,}['\"]",
        "message": "Possible hardcoded secret — use environment variables",
        "severity": "error",
        "file_glob": "*.py",
    },
]


class StandardsEnforcer:
    """Load rules from YAML and check file content for violations."""

    def __init__(self, rules: list[StandardsRule] | None = None) -> None:
        self._rules: list[StandardsRule] = list(rules) if rules else []

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def load_defaults(self) -> None:
        """Load built-in default rules."""
        for r in DEFAULT_RULES:
            self._rules.append(StandardsRule(
                id=r["id"],
                name=r["name"],
                pattern=r["pattern"],
                message=r["message"],
                severity=r.get("severity", "warning"),
                file_glob=r.get("file_glob", "*.py"),
            ))

    def load_yaml(self, yaml_path: str | Path) -> int:
        """Load additional rules from a YAML file. Returns number of rules added."""
        path = Path(yaml_path)
        if not path.is_file():
            return 0
        try:
            if yaml is None:
                raise RuntimeError("PyYAML not installed")
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            rules_data = data.get("rules", []) if isinstance(data, dict) else []
            added = 0
            for r in rules_data:
                self._rules.append(StandardsRule(
                    id=r.get("id", ""),
                    name=r.get("name", ""),
                    pattern=r.get("pattern", ""),
                    message=r.get("message", ""),
                    severity=r.get("severity", "warning"),
                    file_glob=r.get("file_glob", "*.py"),
                ))
                added += 1
            return added
        except Exception:
            return 0

    def list_rules(self) -> list[StandardsRule]:
        return list(self._rules)

    # ------------------------------------------------------------------
    # Checking
    # ------------------------------------------------------------------

    def check_file(self, file_path: str, content: str) -> list[Violation]:
        """Check content of a single file against all applicable rules."""
        violations: list[Violation] = []
        for rule in self._rules:
            try:
                pattern = re.compile(rule.pattern, re.IGNORECASE)
            except re.error:
                continue

            for lineno, line in enumerate(content.splitlines(), start=1):
                m = pattern.search(line)
                if m:
                    violations.append(Violation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        file=file_path,
                        line=lineno,
                        matched_text=m.group(0),
                        message=rule.message,
                        severity=rule.severity,
                    ))
        return violations

    def check_diff(self, files: dict[str, str]) -> list[Violation]:
        """Check a dict of {filename: content} pairs. Returns all violations."""
        all_violations: list[Violation] = []
        for file_path, content in files.items():
            all_violations.extend(self.check_file(file_path, content))
        return all_violations

    # ------------------------------------------------------------------
    # Default YAML content
    # ------------------------------------------------------------------

    @staticmethod
    def default_yaml_content() -> str:
        return (
            "# .lidco/standards.yaml\n"
            "# Coding standards rules\n"
            "rules:\n"
            "  - id: NO_PRINT\n"
            "    name: No print statements\n"
            "    pattern: '\\bprint\\s*\\('\n"
            "    message: Use logging instead of print()\n"
            "    severity: warning\n"
            "    file_glob: '*.py'\n"
            "  - id: NO_HARDCODED_SECRET\n"
            "    name: No hardcoded secrets\n"
            "    pattern: '(password|secret|api_key)\\s*=\\s*[''\"]{1}[^''\"]{{4,}}[''\"]{1}'\n"
            "    message: Possible hardcoded secret\n"
            "    severity: error\n"
            "    file_glob: '*.py'\n"
        )
