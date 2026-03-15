"""Skill version and dependency validation — Task 299.

Checks that a skill's ``requires`` tools are available on PATH,
and validates ``version`` format.

Usage::

    validator = SkillValidator()
    issues = validator.validate(skill)
    if issues:
        print("\\n".join(issues))
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass

from lidco.skills.skill import Skill

_VERSION_RE = re.compile(r"^\d+(\.\d+)*$")

_KNOWN_TOOL_ALIASES: dict[str, list[str]] = {
    "python": ["python3", "python"],
    "git": ["git"],
    "pytest": ["pytest", "python -m pytest"],
    "node": ["node", "nodejs"],
    "npm": ["npm"],
    "docker": ["docker"],
    "make": ["make", "gmake"],
}


@dataclass
class ValidationResult:
    """Result of skill validation."""

    skill_name: str
    issues: list[str]

    @property
    def valid(self) -> bool:
        return len(self.issues) == 0

    def __str__(self) -> str:
        if self.valid:
            return f"Skill '{self.skill_name}': OK"
        return f"Skill '{self.skill_name}': {len(self.issues)} issue(s)\n" + "\n".join(
            f"  · {i}" for i in self.issues
        )


class SkillValidator:
    """Validates skill definitions for correctness and dependency availability."""

    def validate(self, skill: Skill) -> ValidationResult:
        """Run all checks on *skill* and return a ValidationResult."""
        issues: list[str] = []

        # Name check
        if not skill.name or not re.match(r"^[a-z0-9][a-z0-9_-]*$", skill.name):
            issues.append(
                f"Name '{skill.name}' is invalid. Use lowercase letters, digits, hyphens, underscores."
            )

        # Version format check
        if skill.version and not _VERSION_RE.match(str(skill.version)):
            issues.append(f"Version '{skill.version}' is not a valid semver-like format (e.g. 1.0, 2.1.3).")

        # Prompt check
        if not skill.prompt.strip():
            issues.append("Skill has no prompt — add a prompt body or 'prompt:' field.")

        # Requirements check
        for tool in skill.requires:
            if not self._check_tool(tool):
                issues.append(f"Required tool '{tool}' not found on PATH.")

        # Scripts check
        for hook, cmd in skill.scripts.items():
            if hook not in ("pre", "post"):
                issues.append(f"Unknown script hook '{hook}'. Supported: pre, post.")
            if not cmd.strip():
                issues.append(f"Script hook '{hook}' has an empty command.")

        return ValidationResult(skill_name=skill.name, issues=issues)

    def validate_many(self, skills: list[Skill]) -> list[ValidationResult]:
        return [self.validate(s) for s in skills]

    @staticmethod
    def _check_tool(tool: str) -> bool:
        """Return True if *tool* (or one of its known aliases) is on PATH."""
        aliases = _KNOWN_TOOL_ALIASES.get(tool.lower(), [tool])
        return any(shutil.which(a) is not None for a in aliases)
