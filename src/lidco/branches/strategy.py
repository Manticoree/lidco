"""Branch naming strategy engine.

Supports gitflow, github-flow, and trunk-based strategies with
configurable naming rules and auto-creation helpers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


_STRATEGIES: dict[str, dict] = {
    "gitflow": {
        "prefixes": ["feature/", "release/", "hotfix/", "bugfix/", "support/"],
        "protected": ["main", "master", "develop"],
        "pattern": r"^(feature|release|hotfix|bugfix|support)/[a-z0-9][a-z0-9._-]*$",
    },
    "github-flow": {
        "prefixes": ["feature/", "fix/", "chore/", "docs/"],
        "protected": ["main"],
        "pattern": r"^(feature|fix|chore|docs)/[a-z0-9][a-z0-9._-]*$",
    },
    "trunk-based": {
        "prefixes": ["short/"],
        "protected": ["main", "trunk"],
        "pattern": r"^short/[a-z0-9][a-z0-9._-]*$",
    },
}

VALID_STRATEGIES = list(_STRATEGIES.keys())


@dataclass
class BranchStrategy2:
    """Branch naming strategy with validation and auto-creation."""

    _strategy: str = "github-flow"
    _custom_prefixes: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Strategy management
    # ------------------------------------------------------------------

    def set_strategy(self, name: str) -> None:
        """Set the active branching strategy.

        Raises ``ValueError`` for unknown strategy names.
        """
        if name not in _STRATEGIES:
            raise ValueError(
                f"Unknown strategy '{name}'. Valid: {VALID_STRATEGIES}"
            )
        self._strategy = name

    @property
    def strategy(self) -> str:
        return self._strategy

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_name(self, branch: str) -> bool:
        """Return True when *branch* matches the current naming pattern."""
        info = _STRATEGIES[self._strategy]
        return bool(re.match(info["pattern"], branch))

    # ------------------------------------------------------------------
    # Auto-creation helper
    # ------------------------------------------------------------------

    def auto_create(self, type_: str, name: str) -> str:
        """Return a branch name like ``type_/name``.

        Raises ``ValueError`` when *type_* is not an allowed prefix.
        """
        allowed = [p.rstrip("/") for p in self.allowed_prefixes()]
        if type_ not in allowed:
            raise ValueError(
                f"Type '{type_}' not allowed. Allowed: {allowed}"
            )
        slug = re.sub(r"[^a-z0-9._-]", "-", name.lower().strip())
        slug = re.sub(r"-+", "-", slug).strip("-")
        if not slug:
            raise ValueError("Name produces an empty slug after sanitisation.")
        return f"{type_}/{slug}"

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def naming_rules(self) -> dict:
        """Return naming rules for the active strategy."""
        info = _STRATEGIES[self._strategy]
        return {
            "strategy": self._strategy,
            "pattern": info["pattern"],
            "protected": list(info["protected"]),
            "prefixes": list(info["prefixes"]),
        }

    def allowed_prefixes(self) -> list[str]:
        """Return the list of allowed branch prefixes (with trailing slash)."""
        base = list(_STRATEGIES[self._strategy]["prefixes"])
        return base + list(self._custom_prefixes)
