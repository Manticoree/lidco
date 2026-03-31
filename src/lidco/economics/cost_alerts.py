"""Cost Alert Engine — threshold alerts for dollar, %, spike with notification."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class AlertRule:
    """A cost alert rule definition."""

    name: str
    alert_type: str  # "dollar" | "percent" | "spike"
    threshold: float  # dollar amount, percentage (0-100), or multiplier for spike
    channel: str = "console"  # "console" | "webhook"
    webhook_url: str = ""
    cooldown_seconds: float = 300.0  # min time between repeated alerts


@dataclass(frozen=True)
class CostAlert:
    """An emitted cost alert."""

    rule_name: str
    alert_type: str
    message: str
    current_value: float
    threshold: float
    timestamp: float = field(default_factory=time.time)


class CostAlertEngine:
    """Monitors costs and fires alerts when thresholds are crossed.

    Supports:
    - Dollar threshold: alert when cumulative cost exceeds N dollars
    - Percent threshold: alert when cost increase pct exceeds N%
    - Spike detection: alert when per-request cost exceeds N times the average
    """

    def __init__(self) -> None:
        self._rules: dict[str, AlertRule] = {}
        self._cost_history: list[float] = []
        self._total_cost: float = 0.0
        self._last_alert_time: dict[str, float] = {}
        self._listeners: list[Callable[[CostAlert], None]] = []
        self._fired_alerts: list[CostAlert] = []

    # -- Rule management --

    def add_rule(self, rule: AlertRule) -> None:
        """Register an alert rule."""
        self._rules[rule.name] = rule

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name."""
        if name in self._rules:
            del self._rules[name]
            return True
        return False

    def list_rules(self) -> list[AlertRule]:
        """Return all alert rules."""
        return list(self._rules.values())

    def get_rule(self, name: str) -> AlertRule | None:
        """Get a rule by name."""
        return self._rules.get(name)

    # -- Cost recording --

    def record_cost(self, amount: float) -> list[CostAlert]:
        """Record a cost entry and check all alert rules.

        Returns list of alerts fired.
        """
        self._cost_history.append(amount)
        self._total_cost += amount
        now = time.time()
        fired: list[CostAlert] = []

        for rule in self._rules.values():
            # Check cooldown
            last = self._last_alert_time.get(rule.name, 0.0)
            if (now - last) < rule.cooldown_seconds:
                continue

            alert = self._evaluate_rule(rule, amount)
            if alert is not None:
                fired.append(alert)
                self._fired_alerts.append(alert)
                self._last_alert_time[rule.name] = now
                self._notify(alert)

        return fired

    def _evaluate_rule(self, rule: AlertRule, latest_cost: float) -> CostAlert | None:
        if rule.alert_type == "dollar":
            if self._total_cost >= rule.threshold:
                return CostAlert(
                    rule_name=rule.name,
                    alert_type="dollar",
                    message=f"Total cost ${self._total_cost:.4f} exceeds ${rule.threshold:.2f}",
                    current_value=self._total_cost,
                    threshold=rule.threshold,
                )
        elif rule.alert_type == "percent":
            if len(self._cost_history) < 2:
                return None
            prev_total = self._total_cost - latest_cost
            if prev_total <= 0:
                return None
            pct_increase = (latest_cost / prev_total) * 100
            if pct_increase >= rule.threshold:
                return CostAlert(
                    rule_name=rule.name,
                    alert_type="percent",
                    message=f"Cost increase {pct_increase:.1f}% exceeds {rule.threshold:.1f}% threshold",
                    current_value=pct_increase,
                    threshold=rule.threshold,
                )
        elif rule.alert_type == "spike":
            if len(self._cost_history) < 2:
                return None
            avg = sum(self._cost_history[:-1]) / len(self._cost_history[:-1])
            if avg <= 0:
                return None
            multiplier = latest_cost / avg
            if multiplier >= rule.threshold:
                return CostAlert(
                    rule_name=rule.name,
                    alert_type="spike",
                    message=f"Cost spike: ${latest_cost:.4f} is {multiplier:.1f}x average ${avg:.4f}",
                    current_value=multiplier,
                    threshold=rule.threshold,
                )
        return None

    # -- Listeners --

    def add_listener(self, callback: Callable[[CostAlert], None]) -> None:
        """Register a callback for alerts."""
        self._listeners.append(callback)

    def _notify(self, alert: CostAlert) -> None:
        for listener in self._listeners:
            try:
                listener(alert)
            except Exception:
                pass

    # -- Query --

    @property
    def total_cost(self) -> float:
        """Total recorded cost."""
        return self._total_cost

    @property
    def cost_history(self) -> list[float]:
        """All recorded cost entries."""
        return list(self._cost_history)

    @property
    def fired_alerts(self) -> list[CostAlert]:
        """All alerts that have been fired."""
        return list(self._fired_alerts)

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [f"Total cost: ${self._total_cost:.4f}", f"Entries: {len(self._cost_history)}"]
        lines.append(f"Rules: {len(self._rules)}")
        for rule in self._rules.values():
            lines.append(f"  {rule.name}: {rule.alert_type} threshold={rule.threshold}")
        lines.append(f"Alerts fired: {len(self._fired_alerts)}")
        return "\n".join(lines)
