"""Smell catalog — registry of known code smells."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SmellDef:
    """Definition of a single code smell."""

    id: str
    name: str
    severity: str
    description: str
    language: str = "any"
    fix_template: str = ""


class SmellCatalog:
    """Registry of code smell definitions."""

    def __init__(self) -> None:
        self._smells: dict[str, SmellDef] = {}

    # -- mutators (return new-ish state; internal dict is the store) --------

    def register(self, smell: SmellDef) -> None:
        """Register a smell definition."""
        self._smells = {**self._smells, smell.id: smell}

    # -- queries ------------------------------------------------------------

    def get(self, smell_id: str) -> SmellDef | None:
        """Return a smell by *smell_id*, or ``None``."""
        return self._smells.get(smell_id)

    def by_severity(self, severity: str) -> list[SmellDef]:
        """Return all smells matching *severity*."""
        return [s for s in self._smells.values() if s.severity == severity]

    def by_language(self, language: str) -> list[SmellDef]:
        """Return all smells matching *language* (or ``'any'``)."""
        return [
            s
            for s in self._smells.values()
            if s.language == language or s.language == "any"
        ]

    def list_all(self) -> list[SmellDef]:
        """Return every registered smell."""
        return list(self._smells.values())

    # -- factory ------------------------------------------------------------

    @classmethod
    def with_defaults(cls) -> SmellCatalog:
        """Create a catalog pre-populated with ~10 common smells."""
        cat = cls()
        defaults = [
            SmellDef("long_method", "Long Method", "high",
                     "Method exceeds recommended line count", "any",
                     "Extract smaller helper methods"),
            SmellDef("god_class", "God Class", "critical",
                     "Class has too many responsibilities", "any",
                     "Split into focused classes"),
            SmellDef("magic_number", "Magic Number", "medium",
                     "Unexplained numeric literal in code", "any",
                     "Extract to named constant"),
            SmellDef("dead_code", "Dead Code", "medium",
                     "Unreachable or unused code", "any",
                     "Remove dead code"),
            SmellDef("deep_nesting", "Deep Nesting", "high",
                     "Excessive nesting depth", "any",
                     "Use early returns or extract methods"),
            SmellDef("duplicate_code", "Duplicate Code", "high",
                     "Similar code appears in multiple places", "any",
                     "Extract shared utility"),
            SmellDef("feature_envy", "Feature Envy", "medium",
                     "Method uses another class more than its own", "any",
                     "Move method to the envied class"),
            SmellDef("data_clump", "Data Clump", "low",
                     "Same group of data items appears together repeatedly", "any",
                     "Introduce a data class"),
            SmellDef("long_param_list", "Long Parameter List", "medium",
                     "Function takes too many parameters", "any",
                     "Introduce parameter object"),
            SmellDef("commented_code", "Commented-Out Code", "low",
                     "Blocks of commented-out source code", "any",
                     "Remove commented code; use version control"),
        ]
        for s in defaults:
            cat.register(s)
        return cat
