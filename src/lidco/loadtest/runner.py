"""
Q312 Task 1673 — Load Runner

Execute load tests with configurable concurrency and real-time stats.
Supports HTTP, WebSocket, and gRPC protocols (pluggable backends).
Stdlib only — actual I/O is abstracted behind RequestExecutor protocol.
"""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Protocol

from lidco.loadtest.profile import LoadProfile, RequestPattern


# ---------------------------------------------------------------------------
# Protocol — Pluggable executor
# ---------------------------------------------------------------------------


class RequestExecutor(Protocol):
    """
    Pluggable protocol for executing a single request.
    Implementations handle HTTP, WebSocket, gRPC, etc.
    """

    async def execute(self, pattern: RequestPattern) -> RequestResult: ...


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class RequestStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class RequestResult:
    """Outcome of a single request."""

    request_id: str
    url: str
    method: str
    status: RequestStatus
    status_code: int = 0
    latency_ms: float = 0.0
    bytes_received: int = 0
    error: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class LiveStats:
    """Accumulated stats updated in real time."""

    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    timeouts: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0
    bytes_received: int = 0
    start_time: float = 0.0
    elapsed_seconds: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    @property
    def requests_per_second(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return self.total_requests / self.elapsed_seconds

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.failed + self.timeouts) / self.total_requests

    def record(self, result: RequestResult) -> None:
        self.total_requests += 1
        self.total_latency_ms += result.latency_ms
        self.bytes_received += result.bytes_received
        if result.latency_ms < self.min_latency_ms:
            self.min_latency_ms = result.latency_ms
        if result.latency_ms > self.max_latency_ms:
            self.max_latency_ms = result.latency_ms
        if result.status == RequestStatus.SUCCESS:
            self.successful += 1
        elif result.status == RequestStatus.TIMEOUT:
            self.timeouts += 1
        else:
            self.failed += 1


@dataclass
class RunResult:
    """Final result after a load test completes."""

    profile_name: str
    results: list[RequestResult] = field(default_factory=list)
    stats: LiveStats = field(default_factory=LiveStats)
    aborted: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and not self.aborted


# ---------------------------------------------------------------------------
# Default (stub) executor — returns canned results for testing
# ---------------------------------------------------------------------------


class StubExecutor:
    """Stub executor that returns synthetic results."""

    def __init__(
        self,
        latency_ms: float = 50.0,
        error_rate: float = 0.0,
        status_code: int = 200,
    ) -> None:
        self.latency_ms = latency_ms
        self.error_rate = error_rate
        self.status_code = status_code

    async def execute(self, pattern: RequestPattern) -> RequestResult:
        jitter = random.uniform(0.8, 1.2)
        latency = self.latency_ms * jitter
        await asyncio.sleep(latency / 1000.0)

        is_error = random.random() < self.error_rate
        return RequestResult(
            request_id=uuid.uuid4().hex[:12],
            url=pattern.url,
            method=pattern.method.value,
            status=RequestStatus.ERROR if is_error else RequestStatus.SUCCESS,
            status_code=500 if is_error else self.status_code,
            latency_ms=latency,
            bytes_received=0 if is_error else random.randint(100, 2000),
        )


# ---------------------------------------------------------------------------
# Load Runner
# ---------------------------------------------------------------------------


class LoadRunner:
    """
    Execute a LoadProfile using a RequestExecutor.

    Supports:
    - Configurable concurrency per profile schedule
    - Real-time stats callback
    - Abort signal
    - Request timeout
    """

    def __init__(
        self,
        executor: RequestExecutor | None = None,
        request_timeout: float = 30.0,
        stats_callback: Callable[[LiveStats], Any] | None = None,
    ) -> None:
        self.executor: Any = executor or StubExecutor()
        self.request_timeout = request_timeout
        self.stats_callback = stats_callback
        self._aborted = False

    def abort(self) -> None:
        """Signal the runner to stop."""
        self._aborted = True

    async def run(self, profile: LoadProfile) -> RunResult:
        """Execute the load profile and return results."""
        errors = profile.validate()
        if errors:
            return RunResult(
                profile_name=profile.name,
                error=f"Invalid profile: {'; '.join(errors)}",
            )

        self._aborted = False
        stats = LiveStats(start_time=time.time())
        all_results: list[RequestResult] = []
        semaphore = asyncio.Semaphore(profile.max_users)

        total_weight = profile.total_weight()
        if total_weight <= 0:
            return RunResult(
                profile_name=profile.name,
                error="Total request weight is zero",
            )

        start = time.monotonic()

        async def _virtual_user(user_id: int) -> None:
            while not self._aborted:
                elapsed = time.monotonic() - start
                if elapsed >= profile.duration_seconds:
                    break

                current_users = profile.users_at(elapsed)
                if user_id >= current_users:
                    await asyncio.sleep(0.1)
                    continue

                pattern = self._pick_request(profile, total_weight)
                async with semaphore:
                    result = await self._execute_one(pattern)
                    stats.record(result)
                    stats.elapsed_seconds = time.monotonic() - start
                    all_results.append(result)
                    if self.stats_callback:
                        self.stats_callback(stats)

                if profile.think_time_ms > 0:
                    await asyncio.sleep(profile.think_time_ms / 1000.0)

        tasks = [
            asyncio.ensure_future(_virtual_user(uid))
            for uid in range(profile.max_users + getattr(profile, "spike_users", 0))
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        stats.elapsed_seconds = time.monotonic() - start
        return RunResult(
            profile_name=profile.name,
            results=all_results,
            stats=stats,
            aborted=self._aborted,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _pick_request(self, profile: LoadProfile, total_weight: float) -> RequestPattern:
        """Select a request pattern based on weights."""
        if len(profile.requests) == 1:
            return profile.requests[0]
        r = random.uniform(0, total_weight)
        cumulative = 0.0
        for pattern in profile.requests:
            cumulative += pattern.weight
            if r <= cumulative:
                return pattern
        return profile.requests[-1]

    async def _execute_one(self, pattern: RequestPattern) -> RequestResult:
        try:
            return await asyncio.wait_for(
                self.executor.execute(pattern),
                timeout=self.request_timeout,
            )
        except asyncio.TimeoutError:
            return RequestResult(
                request_id=uuid.uuid4().hex[:12],
                url=pattern.url,
                method=pattern.method.value,
                status=RequestStatus.TIMEOUT,
                latency_ms=self.request_timeout * 1000,
                error="Request timed out",
            )
        except Exception as exc:
            return RequestResult(
                request_id=uuid.uuid4().hex[:12],
                url=pattern.url,
                method=pattern.method.value,
                status=RequestStatus.ERROR,
                error=str(exc),
            )
