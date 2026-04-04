"""PRChecklistGenerator — generate PR checklists by type and diff content (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckItem:
    """A single checklist item."""
    category: str
    text: str
    required: bool = True


@dataclass
class Checklist:
    """A full PR checklist."""
    pr_type: str
    items: list[CheckItem] = field(default_factory=list)

    @property
    def required_count(self) -> int:
        return sum(1 for i in self.items if i.required)

    def as_markdown(self) -> str:
        lines = [f"## {self.pr_type} Checklist"]
        for item in self.items:
            prefix = "- [ ]" if item.required else "- [ ] (optional)"
            lines.append(f"{prefix} [{item.category}] {item.text}")
        return "\n".join(lines)


# Default checks by PR type
_DEFAULT_CHECKS: dict[str, list[tuple[str, str]]] = {
    "feature": [
        ("code", "Implementation matches spec"),
        ("tests", "Unit tests added"),
        ("docs", "Documentation updated"),
    ],
    "bugfix": [
        ("code", "Root cause identified"),
        ("tests", "Regression test added"),
        ("code", "No unintended side effects"),
    ],
    "refactor": [
        ("code", "Behavior unchanged"),
        ("tests", "Existing tests pass"),
        ("code", "No dead code introduced"),
    ],
}

_SECURITY_PATTERNS = [
    "password", "secret", "token", "auth", "credential",
    "api_key", "apikey", "private_key",
]

_DEPLOY_PATTERNS = [
    "dockerfile", "docker-compose", "k8s", "kubernetes",
    "deploy", "ci", "cd", "pipeline", "terraform", "helm",
]


class PRChecklistGenerator:
    """Generate checklists for pull requests based on type and diff content."""

    def __init__(self) -> None:
        self._custom_checks: list[CheckItem] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, pr_type: str) -> Checklist:
        """Generate a checklist for the given PR type (feature/bugfix/refactor/unknown)."""
        items: list[CheckItem] = []
        defaults = _DEFAULT_CHECKS.get(pr_type, _DEFAULT_CHECKS.get("feature", []))
        for category, text in defaults:
            items.append(CheckItem(category=category, text=text))
        items = [*items, *self._custom_checks]
        return Checklist(pr_type=pr_type, items=items)

    def add_check(self, category: str, item: str, required: bool = True) -> None:
        """Add a custom check that will be appended to every generated checklist."""
        self._custom_checks = [
            *self._custom_checks,
            CheckItem(category=category, text=item, required=required),
        ]

    def required_checks(self, diff: str) -> list[str]:
        """Return a list of required check descriptions based on diff content."""
        checks: list[str] = ["Code review completed", "Tests pass"]
        if self._has_test_changes(diff):
            checks.append("Test changes reviewed")
        if self._has_config_changes(diff):
            checks.append("Configuration changes validated")
        return checks

    def security_checks(self, diff: str) -> list[str]:
        """Return security-related checks if the diff touches sensitive areas."""
        results: list[str] = []
        lower = diff.lower()
        for pattern in _SECURITY_PATTERNS:
            if pattern in lower:
                results.append(f"Review usage of '{pattern}' — ensure no hardcoded secrets")
        if results:
            results.append("Run security scanner on changed files")
        return results

    def deployment_notes(self, diff: str) -> list[str]:
        """Return deployment-related notes if the diff touches infra/deploy files."""
        notes: list[str] = []
        lower = diff.lower()
        for pattern in _DEPLOY_PATTERNS:
            if pattern in lower:
                notes.append(f"Deployment artifact changed: '{pattern}' — verify in staging")
        if notes:
            notes.append("Coordinate deployment with ops team")
        return notes

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_test_changes(diff: str) -> bool:
        return "test" in diff.lower()

    @staticmethod
    def _has_config_changes(diff: str) -> bool:
        for ext in (".yml", ".yaml", ".toml", ".ini", ".cfg", ".json", ".env"):
            if ext in diff.lower():
                return True
        return False
