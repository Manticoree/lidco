"""Select a model based on complexity, budget and routing rules."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.routing.complexity_estimator import ComplexityResult

_COMPLEXITY_ORDER = {"low": 0, "medium": 1, "high": 2, "expert": 3}

_FALLBACK_MAP: dict[str, list[str]] = {
    "claude-opus-4": ["claude-sonnet-4", "claude-haiku-4-5"],
    "claude-sonnet-4": ["claude-haiku-4-5"],
    "claude-haiku-4-5": [],
}


@dataclass
class RoutingRule:
    """Map a complexity range to a model."""

    min_complexity: str
    max_complexity: str
    model: str
    max_cost: float | None = None


@dataclass(frozen=True)
class ModelSelection:
    """Result of model selection."""

    model: str
    reason: str
    complexity: str
    fallback_chain: list[str] = field(default_factory=list)


def _default_rules() -> list[RoutingRule]:
    return [
        RoutingRule("low", "low", "claude-haiku-4-5"),
        RoutingRule("medium", "medium", "claude-sonnet-4"),
        RoutingRule("high", "high", "claude-sonnet-4"),
        RoutingRule("expert", "expert", "claude-opus-4"),
    ]


class ModelSelector:
    """Select the best model for a task based on complexity and budget."""

    def __init__(
        self,
        rules: list[RoutingRule] | None = None,
        fallback: str = "claude-haiku-4-5",
    ) -> None:
        self._rules: list[RoutingRule] = list(rules) if rules is not None else _default_rules()
        self._fallback = fallback

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select(
        self,
        complexity_result: ComplexityResult,
        budget: float | None = None,
    ) -> ModelSelection:
        """Pick the best model for *complexity_result*."""
        level = complexity_result.level
        level_idx = _COMPLEXITY_ORDER.get(level, 0)

        for rule in self._rules:
            lo = _COMPLEXITY_ORDER.get(rule.min_complexity, 0)
            hi = _COMPLEXITY_ORDER.get(rule.max_complexity, 3)
            if lo <= level_idx <= hi:
                if budget is not None and rule.max_cost is not None and budget > rule.max_cost:
                    continue
                chain = self._build_fallback_chain(rule.model)
                return ModelSelection(
                    model=rule.model,
                    reason=f"complexity={level}, matched rule [{rule.min_complexity}..{rule.max_complexity}]",
                    complexity=level,
                    fallback_chain=chain,
                )

        chain = self._build_fallback_chain(self._fallback)
        return ModelSelection(
            model=self._fallback,
            reason=f"complexity={level}, using fallback",
            complexity=level,
            fallback_chain=chain,
        )

    def add_rule(self, rule: RoutingRule) -> None:
        """Append a routing rule."""
        self._rules = [*self._rules, rule]

    @property
    def rules(self) -> list[RoutingRule]:
        """Return current rules (copy)."""
        return list(self._rules)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_fallback_chain(self, model: str) -> list[str]:
        chain = list(_FALLBACK_MAP.get(model, []))
        if not chain and model != self._fallback:
            chain = [self._fallback]
        return chain
