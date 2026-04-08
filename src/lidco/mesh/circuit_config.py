"""Circuit Breaker Config — generate configs, per-service tuning, historical failure patterns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


@dataclass(frozen=True)
class FailureRecord:
    """Historical failure observation for a service."""

    service: str
    timestamp: float
    error_type: str = "timeout"
    duration_ms: float = 0.0


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Generated circuit breaker configuration for a service."""

    service: str
    failure_threshold: int = 5
    recovery_timeout_s: float = 30.0
    half_open_max_calls: int = 3
    window_size_s: float = 60.0
    min_throughput: int = 10
    error_rate_threshold: float = 0.5
    slow_call_duration_ms: float = 2000.0
    slow_call_rate_threshold: float = 0.5


@dataclass(frozen=True)
class CircuitConfigReport:
    """Report containing generated configs for all services."""

    configs: tuple[CircuitBreakerConfig, ...]
    recommendations: tuple[str, ...]


class CircuitConfigGenerator:
    """Generate circuit breaker configurations based on historical failure patterns."""

    def __init__(self, defaults: CircuitBreakerConfig | None = None) -> None:
        self._defaults = defaults or CircuitBreakerConfig(service="__default__")
        self._failures: list[FailureRecord] = []
        self._overrides: dict[str, dict[str, object]] = {}

    def add_failure(self, record: FailureRecord) -> None:
        """Record a historical failure."""
        self._failures.append(record)

    def add_failures(self, records: Sequence[FailureRecord]) -> None:
        """Record multiple historical failures."""
        self._failures.extend(records)

    def set_override(self, service: str, **kwargs: object) -> None:
        """Set per-service override values."""
        self._overrides[service] = kwargs

    @property
    def failure_count(self) -> int:
        return len(self._failures)

    def _services_from_failures(self) -> set[str]:
        return {f.service for f in self._failures}

    def _failure_rate(self, service: str, window_s: float = 3600.0) -> float:
        """Compute failure frequency (failures per minute) in the window."""
        svc_failures = [f for f in self._failures if f.service == service]
        if not svc_failures or window_s <= 0:
            return 0.0
        return len(svc_failures) / (window_s / 60.0)

    def _avg_failure_duration(self, service: str) -> float:
        durations = [f.duration_ms for f in self._failures
                     if f.service == service and f.duration_ms > 0]
        if not durations:
            return 0.0
        return sum(durations) / len(durations)

    def generate_for_service(self, service: str) -> CircuitBreakerConfig:
        """Generate a tuned circuit breaker config for one service."""
        svc_failures = [f for f in self._failures if f.service == service]
        failure_count = len(svc_failures)

        # Start from defaults
        threshold = self._defaults.failure_threshold
        recovery = self._defaults.recovery_timeout_s
        half_open = self._defaults.half_open_max_calls
        window = self._defaults.window_size_s
        min_tp = self._defaults.min_throughput
        err_rate = self._defaults.error_rate_threshold
        slow_dur = self._defaults.slow_call_duration_ms
        slow_rate = self._defaults.slow_call_rate_threshold

        # Tune based on failure history
        if failure_count > 20:
            # High failure service: more aggressive
            threshold = max(3, threshold - 2)
            recovery = min(recovery * 2, 120.0)
            err_rate = max(0.2, err_rate - 0.15)
        elif failure_count > 10:
            threshold = max(3, threshold - 1)
            recovery = min(recovery * 1.5, 90.0)

        avg_dur = self._avg_failure_duration(service)
        if avg_dur > 5000:
            slow_dur = avg_dur * 0.8
            slow_rate = 0.3

        # Apply overrides
        overrides = self._overrides.get(service, {})
        if "failure_threshold" in overrides:
            threshold = int(overrides["failure_threshold"])  # type: ignore[arg-type]
        if "recovery_timeout_s" in overrides:
            recovery = float(overrides["recovery_timeout_s"])  # type: ignore[arg-type]
        if "half_open_max_calls" in overrides:
            half_open = int(overrides["half_open_max_calls"])  # type: ignore[arg-type]

        return CircuitBreakerConfig(
            service=service,
            failure_threshold=threshold,
            recovery_timeout_s=round(recovery, 1),
            half_open_max_calls=half_open,
            window_size_s=window,
            min_throughput=min_tp,
            error_rate_threshold=round(err_rate, 2),
            slow_call_duration_ms=round(slow_dur, 1),
            slow_call_rate_threshold=round(slow_rate, 2),
        )

    def generate(self, services: Sequence[str] | None = None) -> CircuitConfigReport:
        """Generate configs for all known services (or the given list)."""
        svc_names = set(services) if services else self._services_from_failures()
        if not svc_names:
            return CircuitConfigReport(configs=(), recommendations=("No failure data available.",))

        configs: list[CircuitBreakerConfig] = []
        recommendations: list[str] = []

        for name in sorted(svc_names):
            cfg = self.generate_for_service(name)
            configs.append(cfg)
            svc_failures = [f for f in self._failures if f.service == name]
            if len(svc_failures) > 20:
                recommendations.append(
                    f"{name}: high failure count ({len(svc_failures)}), "
                    f"consider investigating root cause"
                )

        return CircuitConfigReport(
            configs=tuple(configs),
            recommendations=tuple(recommendations),
        )
