"""Rate Limit Generator — per-endpoint configs, capacity, burst handling, priority lanes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence


class PriorityLane(Enum):
    """Request priority lanes."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


@dataclass(frozen=True)
class EndpointCapacity:
    """Observed capacity info for an endpoint."""

    service: str
    endpoint: str
    max_rps: float
    avg_rps: float = 0.0
    p99_latency_ms: float = 0.0


@dataclass(frozen=True)
class RateLimitConfig:
    """Generated rate limit configuration for an endpoint."""

    service: str
    endpoint: str
    requests_per_second: float
    burst_size: int
    window_s: float = 1.0
    priority: PriorityLane = PriorityLane.NORMAL
    retry_after_s: float = 1.0


@dataclass(frozen=True)
class RateLimitReport:
    """Full rate limit report for all endpoints."""

    configs: tuple[RateLimitConfig, ...]
    total_endpoints: int
    recommendations: tuple[str, ...]


class RateLimitGenerator:
    """Generate rate limit configurations based on capacity and patterns."""

    def __init__(self, safety_margin: float = 0.8) -> None:
        """
        Args:
            safety_margin: Fraction of max capacity to use as limit (0.0-1.0).
        """
        if not 0.0 < safety_margin <= 1.0:
            raise ValueError("safety_margin must be in (0.0, 1.0]")
        self._safety_margin = safety_margin
        self._capacities: list[EndpointCapacity] = []
        self._priority_overrides: dict[tuple[str, str], PriorityLane] = {}
        self._burst_multiplier: float = 2.0

    def add_capacity(self, capacity: EndpointCapacity) -> None:
        """Record endpoint capacity observation."""
        self._capacities.append(capacity)

    def add_capacities(self, capacities: Sequence[EndpointCapacity]) -> None:
        """Record multiple capacity observations."""
        self._capacities.extend(capacities)

    def set_priority(self, service: str, endpoint: str, priority: PriorityLane) -> None:
        """Set priority lane for an endpoint."""
        self._priority_overrides[(service, endpoint)] = priority

    def set_burst_multiplier(self, multiplier: float) -> None:
        """Set burst size multiplier (burst_size = rps * multiplier)."""
        if multiplier < 1.0:
            raise ValueError("burst_multiplier must be >= 1.0")
        self._burst_multiplier = multiplier

    @property
    def endpoint_count(self) -> int:
        return len(self._capacities)

    def _priority_factor(self, priority: PriorityLane) -> float:
        """Priority lanes get different fractions of capacity."""
        factors = {
            PriorityLane.CRITICAL: 1.0,
            PriorityLane.HIGH: 0.9,
            PriorityLane.NORMAL: 0.8,
            PriorityLane.LOW: 0.5,
            PriorityLane.BACKGROUND: 0.2,
        }
        return factors.get(priority, 0.8)

    def generate_for_endpoint(self, capacity: EndpointCapacity) -> RateLimitConfig:
        """Generate rate limit config for a single endpoint."""
        priority = self._priority_overrides.get(
            (capacity.service, capacity.endpoint), PriorityLane.NORMAL
        )
        p_factor = self._priority_factor(priority)
        rps = capacity.max_rps * self._safety_margin * p_factor
        rps = max(1.0, round(rps, 1))
        burst = max(1, int(rps * self._burst_multiplier))

        # Retry-after scales with latency
        retry_after = 1.0
        if capacity.p99_latency_ms > 2000:
            retry_after = 5.0
        elif capacity.p99_latency_ms > 500:
            retry_after = 2.0

        return RateLimitConfig(
            service=capacity.service,
            endpoint=capacity.endpoint,
            requests_per_second=rps,
            burst_size=burst,
            priority=priority,
            retry_after_s=retry_after,
        )

    def generate(self) -> RateLimitReport:
        """Generate rate limit configs for all observed endpoints."""
        if not self._capacities:
            return RateLimitReport(
                configs=(), total_endpoints=0,
                recommendations=("No capacity data available.",),
            )

        configs: list[RateLimitConfig] = []
        recommendations: list[str] = []

        for cap in self._capacities:
            cfg = self.generate_for_endpoint(cap)
            configs.append(cfg)
            if cap.max_rps < 10:
                recommendations.append(
                    f"{cap.service}/{cap.endpoint}: very low capacity "
                    f"({cap.max_rps} rps), consider scaling"
                )
            if cap.p99_latency_ms > 5000:
                recommendations.append(
                    f"{cap.service}/{cap.endpoint}: very high p99 latency "
                    f"({cap.p99_latency_ms}ms), investigate bottlenecks"
                )

        return RateLimitReport(
            configs=tuple(configs),
            total_endpoints=len(configs),
            recommendations=tuple(recommendations),
        )
