"""TypeMigration — modernise type annotations via regex rules (stdlib only)."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MigrationRule:
    """A single search-and-replace migration rule."""

    pattern: str
    replacement: str
    description: str


# Default rules: PEP 604 + PEP 585.
_DEFAULT_RULES: list[MigrationRule] = [
    # PEP 604: Optional[X] -> X | None  (handles nested brackets)
    MigrationRule(
        pattern=r"Optional\[((?:[^\[\]]|\[[^\[\]]*\])+)\]",
        replacement=r"\1 | None",
        description="PEP 604: Optional[X] -> X | None",
    ),
    # PEP 604: Union[X, Y] -> X | Y  (handles nested brackets)
    MigrationRule(
        pattern=r"Union\[((?:[^\[\],]|\[[^\[\]]*\])+),\s*((?:[^\[\]]|\[[^\[\]]*\])+)\]",
        replacement=r"\1 | \2",
        description="PEP 604: Union[X, Y] -> X | Y",
    ),
    # PEP 585: Dict[K, V] -> dict[K, V]
    MigrationRule(
        pattern=r"\bDict\[",
        replacement="dict[",
        description="PEP 585: Dict -> dict",
    ),
    # PEP 585: List[X] -> list[X]
    MigrationRule(
        pattern=r"\bList\[",
        replacement="list[",
        description="PEP 585: List -> list",
    ),
    # PEP 585: Tuple[X, ...] -> tuple[X, ...]
    MigrationRule(
        pattern=r"\bTuple\[",
        replacement="tuple[",
        description="PEP 585: Tuple -> tuple",
    ),
    # PEP 585: Set[X] -> set[X]
    MigrationRule(
        pattern=r"\bSet\[",
        replacement="set[",
        description="PEP 585: Set -> set",
    ),
    # PEP 585: FrozenSet[X] -> frozenset[X]
    MigrationRule(
        pattern=r"\bFrozenSet\[",
        replacement="frozenset[",
        description="PEP 585: FrozenSet -> frozenset",
    ),
    # PEP 585: Type[X] -> type[X]
    MigrationRule(
        pattern=r"\bType\[",
        replacement="type[",
        description="PEP 585: Type -> type",
    ),
]


class TypeMigration:
    """Apply type-annotation migration rules to Python source."""

    def __init__(self, rules: list[MigrationRule] | None = None) -> None:
        self._rules: list[MigrationRule] = list(rules) if rules is not None else []

    @classmethod
    def with_defaults(cls) -> TypeMigration:
        """Create an instance pre-loaded with PEP 585 + PEP 604 rules."""
        return cls(rules=list(_DEFAULT_RULES))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply(self, source: str) -> str:
        """Apply all rules to *source* and return the migrated text."""
        result = source
        for rule in self._rules:
            result = self.apply_rule(result, rule)
        return result

    @staticmethod
    def apply_rule(source: str, rule: MigrationRule) -> str:
        """Apply a single *rule* to *source*."""
        return re.sub(rule.pattern, rule.replacement, source)

    def preview(self, source: str) -> list[dict[str, str]]:
        """Show what each rule would change without modifying *source*."""
        changes: list[dict[str, str]] = []
        for rule in self._rules:
            migrated = re.sub(rule.pattern, rule.replacement, source)
            if migrated != source:
                changes.append({
                    "description": rule.description,
                    "pattern": rule.pattern,
                    "replacement": rule.replacement,
                })
        return changes

    def list_rules(self) -> list[MigrationRule]:
        """Return a copy of all current rules."""
        return list(self._rules)
