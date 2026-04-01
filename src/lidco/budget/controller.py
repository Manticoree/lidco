"""Unified budget controller -- facade over all budget modules."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TurnResult:
    """Immutable result from processing a single turn."""

    turn: int = 0
    tokens_used: int = 0
    tokens_remaining: int = 0
    compacted: bool = False
    alerts: tuple[str, ...] = ()
    utilization: float = 0.0


class BudgetController:
    """Facade that coordinates meter, alerter, orchestrator, forecaster, and debt."""

    def __init__(
        self,
        context_limit: int = 128_000,
        thresholds: tuple[float, ...] = (0.70, 0.85, 0.95),
    ) -> None:
        from lidco.budget.window_meter import ContextWindowMeter
        from lidco.budget.threshold_alerter import ThresholdAlerter
        from lidco.budget.compaction_orchestrator import CompactionOrchestrator
        from lidco.budget.budget_forecaster import BudgetForecaster
        from lidco.budget.token_debt import TokenDebtTracker

        self._meter = ContextWindowMeter(context_limit=context_limit)
        self._alerter = ThresholdAlerter(thresholds=thresholds)
        self._orchestrator = CompactionOrchestrator(
            warn_threshold=thresholds[0] if len(thresholds) >= 1 else 0.70,
            critical_threshold=thresholds[1] if len(thresholds) >= 2 else 0.85,
            emergency_threshold=thresholds[2] if len(thresholds) >= 3 else 0.95,
        )
        self._forecaster = BudgetForecaster(total_budget=context_limit)
        self._debt = TokenDebtTracker()
        self._turn = 0

    def process_turn(self, role: str, tokens: int) -> TurnResult:
        """Record tokens, check thresholds, check compaction, return result."""
        self._meter.record(role, tokens)
        self._turn += 1

        util = self._meter.utilization()
        alert = self._alerter.check(util)
        alerts = (alert.message,) if alert is not None else ()

        trigger = self._orchestrator.should_compact(util)
        compacted = trigger is not None

        self._forecaster.record(self._meter.used)

        return TurnResult(
            turn=self._turn,
            tokens_used=self._meter.used,
            tokens_remaining=self._meter.remaining,
            compacted=compacted,
            alerts=alerts,
            utilization=round(util, 4),
        )

    def should_compact(self) -> bool:
        """Whether the orchestrator recommends compaction now."""
        return self._orchestrator.should_compact(self._meter.utilization()) is not None

    def record_compaction(self, before: int, after: int) -> None:
        """Update meter and orchestrator after a compaction."""
        from lidco.budget.compaction_orchestrator import CompactionTrigger

        saved = before - after
        self._meter.remove("assistant", saved)
        strategy = self._orchestrator.select_strategy(self._meter.utilization())
        trigger = self._orchestrator.should_compact(self._meter.utilization())
        if trigger is None:
            trigger = CompactionTrigger.MANUAL
        self._orchestrator.record_compaction(
            trigger=trigger,
            before=before,
            after=after,
            strategy=strategy,
        )

    def get_forecast(self) -> dict:
        """Delegate to forecaster and return as dict."""
        fc = self._forecaster.forecast()
        return {
            "current_used": fc.current_used,
            "total_budget": fc.total_budget,
            "burn_rate": fc.burn_rate,
            "estimated_turns_remaining": fc.estimated_turns_remaining,
            "recommendation": fc.recommendation,
        }

    def incur_debt(self, amount: int, reason: str = "") -> None:
        """Delegate to debt tracker."""
        self._debt.incur(amount, reason)

    def outstanding_debt(self) -> int:
        """Return outstanding token debt."""
        return self._debt.outstanding()

    def utilization(self) -> float:
        """Current utilization ratio."""
        return self._meter.utilization()

    def remaining(self) -> int:
        """Tokens remaining in budget."""
        return self._meter.remaining

    def reset(self) -> None:
        """Reset all internal state."""
        self._meter.reset()
        self._alerter.reset()
        self._forecaster = type(self._forecaster)(total_budget=self._forecaster._total)
        self._debt.clear()
        self._turn = 0

    def summary(self) -> str:
        """Combined summary from meter, alerter, and debt."""
        parts = [
            self._meter.summary(),
            self._alerter.summary(),
            self._debt.summary(),
        ]
        return "\n".join(parts)
