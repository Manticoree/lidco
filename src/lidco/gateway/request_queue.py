"""RequestQueue — Queue requests with priority, timeout, and retry with backoff."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class QueuedRequest:
    id: str
    provider: str
    payload: str
    priority: int = 0
    retries: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)
    timeout: float = 30.0


class RequestQueue:
    """Priority queue for rate-limited API requests with retry and backoff."""

    def __init__(self, max_size: int = 1000, backoff_base: float = 1.0) -> None:
        self._max_size = max_size
        self._backoff_base = backoff_base
        self._queue: list[QueuedRequest] = []
        self._cancelled: set[str] = set()

    def enqueue(
        self,
        provider: str,
        payload: str,
        priority: int = 0,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> QueuedRequest:
        """Add a request to the queue."""
        if len(self._queue) >= self._max_size:
            raise ValueError(f"Queue full (max_size={self._max_size})")
        req = QueuedRequest(
            id=uuid.uuid4().hex[:12],
            provider=provider,
            payload=payload,
            priority=priority,
            max_retries=max_retries,
            timeout=timeout,
        )
        self._queue.append(req)
        return req

    def dequeue(self) -> QueuedRequest | None:
        """Remove and return the highest-priority, non-timed-out request."""
        self.expire_timeouts()
        if not self._queue:
            return None
        # Sort by priority descending (highest first)
        self._queue.sort(key=lambda r: r.priority, reverse=True)
        return self._queue.pop(0)

    def retry(self, request_id: str) -> QueuedRequest | None:
        """Re-enqueue a request with incremented retries and backoff delay."""
        for req in self._queue:
            if req.id == request_id:
                if req.retries >= req.max_retries:
                    return None
                req.retries += 1
                # Apply backoff: extend timeout by backoff_base * 2^retries
                req.created_at = time.time()
                req.timeout = req.timeout + self._backoff_base * (2 ** req.retries)
                return req
        return None

    def cancel(self, request_id: str) -> bool:
        """Cancel a queued request."""
        for i, req in enumerate(self._queue):
            if req.id == request_id:
                self._queue.pop(i)
                self._cancelled.add(request_id)
                return True
        return False

    def expire_timeouts(self) -> int:
        """Remove timed-out requests. Returns count removed."""
        now = time.time()
        before = len(self._queue)
        self._queue = [
            r for r in self._queue
            if (now - r.created_at) < r.timeout
        ]
        return before - len(self._queue)

    def size(self) -> int:
        """Current queue size."""
        return len(self._queue)

    def pending(self, provider: str | None = None) -> list[QueuedRequest]:
        """Return pending requests, optionally filtered by provider."""
        if provider is None:
            return list(self._queue)
        return [r for r in self._queue if r.provider == provider]

    def summary(self) -> dict:
        """Summary of queue state."""
        providers: dict[str, int] = {}
        for r in self._queue:
            providers[r.provider] = providers.get(r.provider, 0) + 1
        return {
            "size": len(self._queue),
            "max_size": self._max_size,
            "cancelled": len(self._cancelled),
            "providers": providers,
        }
