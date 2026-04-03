"""ModelPool — multi-model pool with selection strategies and health tracking."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelEntry:
    """Immutable snapshot of a model in the pool."""

    name: str
    status: str = "healthy"
    latency_ms: float = 0.0
    request_count: int = 0


class ModelPool:
    """Manages a pool of models with round-robin / least-loaded selection."""

    def __init__(self) -> None:
        self._models: dict[str, ModelEntry] = {}
        self._rr_index: int = 0

    # -- mutators (return new pool state internally) -----------------------

    def add(self, name: str) -> bool:
        """Add a model. Returns False if already present."""
        if name in self._models:
            return False
        self._models = {**self._models, name: ModelEntry(name=name)}
        return True

    def remove(self, name: str) -> bool:
        """Remove a model. Returns False if not found."""
        if name not in self._models:
            return False
        self._models = {k: v for k, v in self._models.items() if k != name}
        return True

    # -- selection ---------------------------------------------------------

    def select(self, strategy: str = "round_robin") -> str | None:
        """Select a healthy model using *strategy*."""
        healthy = [e for e in self._models.values() if e.status == "healthy"]
        if not healthy:
            return None

        if strategy == "least_loaded":
            chosen = min(healthy, key=lambda e: e.request_count)
        else:  # round_robin
            idx = self._rr_index % len(healthy)
            chosen = healthy[idx]
            self._rr_index = idx + 1

        # bump request count immutably
        updated = ModelEntry(
            name=chosen.name,
            status=chosen.status,
            latency_ms=chosen.latency_ms,
            request_count=chosen.request_count + 1,
        )
        self._models = {**self._models, chosen.name: updated}
        return chosen.name

    # -- health ------------------------------------------------------------

    def health_check(self, name: str) -> bool:
        """Return True if *name* exists and is healthy."""
        entry = self._models.get(name)
        return entry is not None and entry.status == "healthy"

    def mark_unhealthy(self, name: str) -> None:
        entry = self._models.get(name)
        if entry is None:
            return
        self._models = {
            **self._models,
            name: ModelEntry(
                name=entry.name,
                status="unhealthy",
                latency_ms=entry.latency_ms,
                request_count=entry.request_count,
            ),
        }

    def mark_healthy(self, name: str) -> None:
        entry = self._models.get(name)
        if entry is None:
            return
        self._models = {
            **self._models,
            name: ModelEntry(
                name=entry.name,
                status="healthy",
                latency_ms=entry.latency_ms,
                request_count=entry.request_count,
            ),
        }

    # -- queries -----------------------------------------------------------

    def list_models(self) -> list[ModelEntry]:
        return list(self._models.values())

    def stats(self) -> dict:
        total = len(self._models)
        healthy = sum(1 for e in self._models.values() if e.status == "healthy")
        return {
            "total": total,
            "healthy": healthy,
            "unhealthy": total - healthy,
            "total_requests": sum(e.request_count for e in self._models.values()),
        }
