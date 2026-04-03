"""ApiGateway — Route requests to providers with load balancing and circuit breaker."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field


@dataclass
class Endpoint:
    name: str
    url: str
    healthy: bool = True
    weight: int = 1
    failure_count: int = 0
    last_check: float = 0.0


@dataclass(frozen=True)
class GatewayRequest:
    provider: str
    path: str
    method: str = "POST"
    headers: dict | None = None
    body: str | None = None


@dataclass(frozen=True)
class GatewayResponse:
    status: int
    body: str
    endpoint: str
    latency_ms: float


class ApiGateway:
    """Route requests to healthy endpoints with weighted selection and circuit breaker."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._endpoints: dict[str, Endpoint] = {}

    def add_endpoint(self, name: str, url: str, weight: int = 1) -> Endpoint:
        """Register an endpoint."""
        ep = Endpoint(name=name, url=url, weight=weight)
        self._endpoints[name] = ep
        return ep

    def remove_endpoint(self, name: str) -> bool:
        """Remove an endpoint by name. Returns True if it existed."""
        return self._endpoints.pop(name, None) is not None

    def select_endpoint(self, provider: str | None = None) -> Endpoint | None:
        """Weighted random selection among healthy endpoints."""
        candidates = self.healthy_endpoints()
        if provider is not None:
            candidates = [ep for ep in candidates if ep.name == provider]
        if not candidates:
            return None
        weights = [ep.weight for ep in candidates]
        total = sum(weights)
        r = random.random() * total
        cumulative = 0.0
        for ep in candidates:
            cumulative += ep.weight
            if r <= cumulative:
                return ep
        return candidates[-1]

    def mark_failure(self, name: str) -> Endpoint:
        """Increment failure count; mark unhealthy at threshold."""
        ep = self._endpoints[name]
        ep.failure_count += 1
        if ep.failure_count >= self._failure_threshold:
            ep.healthy = False
            ep.last_check = time.monotonic()
        return ep

    def mark_success(self, name: str) -> Endpoint:
        """Reset failures and mark healthy."""
        ep = self._endpoints[name]
        ep.failure_count = 0
        ep.healthy = True
        return ep

    def check_health(self, name: str) -> bool:
        """Check if recovery timeout passed for unhealthy endpoint; attempt recovery."""
        ep = self._endpoints[name]
        if ep.healthy:
            return True
        now = time.monotonic()
        if now - ep.last_check >= self._recovery_timeout:
            ep.healthy = True
            ep.failure_count = 0
            ep.last_check = now
            return True
        return False

    def healthy_endpoints(self) -> list[Endpoint]:
        """Return all healthy endpoints."""
        return [ep for ep in self._endpoints.values() if ep.healthy]

    def all_endpoints(self) -> list[Endpoint]:
        """Return all registered endpoints."""
        return list(self._endpoints.values())

    def summary(self) -> dict:
        """Summary of gateway state."""
        total = len(self._endpoints)
        healthy = len(self.healthy_endpoints())
        return {
            "total": total,
            "healthy": healthy,
            "unhealthy": total - healthy,
            "endpoints": [
                {"name": ep.name, "url": ep.url, "healthy": ep.healthy, "weight": ep.weight}
                for ep in self._endpoints.values()
            ],
        }
