"""Context usage threshold alerts with escalation."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class AlertLevel(str, Enum):
    """Severity level for context alerts."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ThresholdAlert:
    """Immutable alert record."""

    level: AlertLevel
    threshold: float
    current: float
    message: str
    timestamp: float = field(default_factory=time.time)


def _level_for_threshold(threshold: float) -> AlertLevel:
    """Determine alert level based on threshold value."""
    if threshold >= 0.90:
        return AlertLevel.CRITICAL
    if threshold >= 0.80:
        return AlertLevel.WARNING
    return AlertLevel.INFO


class ThresholdAlerter:
    """Monitors context utilization and fires alerts on threshold crossings."""

    def __init__(
        self,
        thresholds: tuple[float, ...] = (0.70, 0.85, 0.95),
    ) -> None:
        self._thresholds = tuple(sorted(thresholds))
        self._fired: dict[float, float] = {}  # threshold -> last fired timestamp
        self._alerts: list[ThresholdAlert] = []
        self._cooldown: float = 60.0

    def check(self, utilization: float) -> ThresholdAlert | None:
        """Check utilization against thresholds. Return alert if newly crossed."""
        now = time.time()
        for threshold in reversed(self._thresholds):
            if utilization >= threshold:
                last_fired = self._fired.get(threshold, 0.0)
                if now - last_fired >= self._cooldown:
                    level = _level_for_threshold(threshold)
                    alert = ThresholdAlert(
                        level=level,
                        threshold=threshold,
                        current=utilization,
                        message=(
                            f"Context usage at {utilization * 100:.1f}% "
                            f"(threshold: {threshold * 100:.0f}%)"
                        ),
                    )
                    self._fired = {**self._fired, threshold: now}
                    self._alerts = [*self._alerts, alert]
                    return alert
        return None

    def get_alerts(self, limit: int = 20) -> list[ThresholdAlert]:
        """Return last *limit* alerts."""
        return list(self._alerts[-limit:])

    def reset(self) -> None:
        """Clear fired state and alerts."""
        self._fired = {}
        self._alerts = []

    def set_thresholds(self, thresholds: tuple[float, ...]) -> None:
        """Replace thresholds and reset fired state."""
        self._thresholds = tuple(sorted(thresholds))
        self._fired = {}

    def is_critical(self, utilization: float) -> bool:
        """True if utilization exceeds the highest threshold."""
        if not self._thresholds:
            return False
        return utilization >= self._thresholds[-1]

    def summary(self) -> str:
        """Human-readable summary of alerter state."""
        lines = [f"Threshold Alerter ({len(self._thresholds)} thresholds):"]
        for t in self._thresholds:
            fired = t in self._fired
            status = "FIRED" if fired else "armed"
            lines.append(f"  {t * 100:.0f}%: {status}")
        lines.append(f"  Total alerts: {len(self._alerts)}")
        return "\n".join(lines)
