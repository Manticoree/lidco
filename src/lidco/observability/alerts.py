"""Q297 -- AlertManager2: alert rules, evaluation, silencing, escalation."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Condition(Enum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"


@dataclass
class Rule:
    """An alert rule definition."""

    rule_id: str
    name: str
    condition: str  # Condition value
    threshold: float
    severity: AlertSeverity = AlertSeverity.WARNING
    metric_name: str = ""
    silenced_until: float = 0.0

    @property
    def is_silenced(self) -> bool:
        return self.silenced_until > time.time()


@dataclass
class Alert:
    """A fired alert."""

    alert_id: str
    rule_id: str
    rule_name: str
    metric_name: str
    value: float
    threshold: float
    severity: str
    fired_at: float
    escalated: bool = False


class AlertManager2:
    """Manage alert rules, evaluate metrics, silence and escalate."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}
        self._alerts: list[Alert] = []

    # -- rules -------------------------------------------------------------

    def add_rule(
        self,
        name: str,
        condition: str,
        threshold: float,
        *,
        metric_name: str = "",
        severity: AlertSeverity = AlertSeverity.WARNING,
    ) -> Rule:
        """Create and register an alert rule.  Returns the Rule."""
        rule_id = uuid.uuid4().hex[:12]
        rule = Rule(
            rule_id=rule_id,
            name=name,
            condition=condition,
            threshold=threshold,
            severity=severity,
            metric_name=metric_name,
        )
        self._rules[rule_id] = rule
        return rule

    # -- evaluation --------------------------------------------------------

    def evaluate(self, metric_name: str, value: float) -> list[Alert]:
        """Evaluate all rules for *metric_name* against *value*.  Returns new alerts."""
        new_alerts: list[Alert] = []
        for rule in self._rules.values():
            if rule.is_silenced:
                continue
            if rule.metric_name and rule.metric_name != metric_name:
                continue
            if self._check(value, rule.condition, rule.threshold):
                alert = Alert(
                    alert_id=uuid.uuid4().hex[:12],
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    metric_name=metric_name,
                    value=value,
                    threshold=rule.threshold,
                    severity=rule.severity.value,
                    fired_at=time.time(),
                )
                self._alerts.append(alert)
                new_alerts.append(alert)
        return new_alerts

    # -- silencing ---------------------------------------------------------

    def silence(self, rule_id: str, duration: float) -> None:
        """Silence a rule for *duration* seconds."""
        rule = self._rules.get(rule_id)
        if rule is None:
            raise KeyError(f"Unknown rule_id: {rule_id}")
        rule.silenced_until = time.time() + duration

    # -- queries -----------------------------------------------------------

    def active_alerts(self) -> list[Alert]:
        """Return all non-escalated alerts, newest first."""
        return sorted(
            [a for a in self._alerts if not a.escalated],
            key=lambda a: a.fired_at,
            reverse=True,
        )

    def escalate(self, alert_id: str) -> bool:
        """Mark an alert as escalated.  Returns True if found."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.escalated = True
                return True
        return False

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _check(value: float, condition: str, threshold: float) -> bool:
        if condition == "gt":
            return value > threshold
        if condition == "gte":
            return value >= threshold
        if condition == "lt":
            return value < threshold
        if condition == "lte":
            return value <= threshold
        if condition == "eq":
            return value == threshold
        return False
