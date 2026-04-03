"""CascadeRouter — ordered fallback routing across models."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CascadeRule:
    """One step in the cascade chain."""

    model: str
    timeout: float = 30.0
    fallback_on: list[str] = field(default_factory=lambda: ["error", "timeout"])


@dataclass(frozen=True)
class CascadeResult:
    """Outcome of a routed request."""

    model_used: str
    attempts: list[dict]
    success: bool


class CascadeRouter:
    """Route requests through an ordered cascade of models with fallback."""

    def __init__(self) -> None:
        self._rules: list[CascadeRule] = []

    def add_rule(self, rule: CascadeRule) -> None:
        self._rules = [*self._rules, rule]

    def route(self, request: str) -> CascadeResult:
        """Try each rule in order; first success wins.

        Simulation: odd-length model names succeed, even-length fail.
        """
        if not self._rules:
            return CascadeResult(model_used="", attempts=[], success=False)

        attempts: list[dict] = []
        for rule in self._rules:
            # Simulate: model succeeds when name length is odd
            ok = len(rule.model) % 2 == 1
            attempts = [
                *attempts,
                {"model": rule.model, "success": ok, "request": request},
            ]
            if ok:
                return CascadeResult(
                    model_used=rule.model, attempts=attempts, success=True
                )

        # All failed — report last model
        return CascadeResult(
            model_used=self._rules[-1].model, attempts=attempts, success=False
        )

    def simulate(self, request: str) -> list[str]:
        """Return the ordered list of models that would be tried."""
        return [r.model for r in self._rules]

    def list_rules(self) -> list[CascadeRule]:
        return list(self._rules)
