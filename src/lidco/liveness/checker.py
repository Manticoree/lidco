"""Liveness Checker — verify external services/URLs are reachable (stdlib only).

Like Kubernetes readiness probes or Docker HEALTHCHECK: define a set of
endpoints/hosts to probe, run checks, and get structured health reports.
Supports HTTP(S) checks, TCP port checks, and custom callables.
"""
from __future__ import annotations

import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class CheckError(Exception):
    """Raised when a liveness check configuration is invalid."""


class CheckStatus(str, Enum):
    UP = "up"
    DOWN = "down"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class CheckResult:
    """Result of a single liveness check."""

    name: str
    status: CheckStatus
    latency_ms: float = 0.0
    message: str = ""
    checked_at: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_up(self) -> bool:
        return self.status == CheckStatus.UP

    def format(self) -> str:
        icon = "✓" if self.is_up else "✗"
        msg = f" — {self.message}" if self.message else ""
        return f"{icon} {self.name}: {self.status.value} ({self.latency_ms:.0f}ms){msg}"


@dataclass
class HealthReport:
    """Aggregate report from running all registered checks."""

    results: list[CheckResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0

    @property
    def all_up(self) -> bool:
        return all(r.is_up for r in self.results)

    @property
    def up_count(self) -> int:
        return sum(1 for r in self.results if r.is_up)

    @property
    def down_count(self) -> int:
        return len(self.results) - self.up_count

    @property
    def duration_ms(self) -> float:
        return (self.finished_at - self.started_at) * 1000

    def summary(self) -> str:
        total = len(self.results)
        status = "HEALTHY" if self.all_up else "DEGRADED"
        return (
            f"[{status}] {self.up_count}/{total} up "
            f"({self.down_count} down, {self.duration_ms:.0f}ms total)"
        )

    def format(self) -> str:
        lines = [self.summary()]
        for r in self.results:
            lines.append(f"  {r.format()}")
        return "\n".join(lines)


CheckFn = Callable[[], CheckResult]


class LivenessChecker:
    """Register and run health checks for external dependencies.

    Usage::

        checker = LivenessChecker(timeout=5.0)
        checker.add_http("api", "https://httpbin.org/get")
        checker.add_tcp("db", "localhost", 5432)
        checker.add_custom("redis", lambda: check_redis())

        report = checker.run_all()
        print(report.format())
    """

    def __init__(self, timeout: float = 5.0) -> None:
        if timeout <= 0:
            raise CheckError("timeout must be > 0")
        self._timeout = timeout
        self._checks: dict[str, CheckFn] = {}

    # ------------------------------------------------------------------ #
    # Registration                                                         #
    # ------------------------------------------------------------------ #

    def add_http(
        self,
        name: str,
        url: str,
        expected_status: int = 200,
        method: str = "GET",
    ) -> None:
        """Register an HTTP(S) endpoint check."""
        if not name:
            raise CheckError("check name must not be empty")
        self._checks[name] = self._make_http_check(name, url, expected_status)

    def add_tcp(self, name: str, host: str, port: int) -> None:
        """Register a TCP port reachability check."""
        if not name:
            raise CheckError("check name must not be empty")
        if not 1 <= port <= 65535:
            raise CheckError(f"invalid port: {port}")
        self._checks[name] = self._make_tcp_check(name, host, port)

    def add_custom(self, name: str, fn: CheckFn) -> None:
        """Register a custom check function."""
        if not name:
            raise CheckError("check name must not be empty")
        self._checks[name] = fn

    def remove(self, name: str) -> bool:
        return self._checks.pop(name, None) is not None

    def list_checks(self) -> list[str]:
        return list(self._checks.keys())

    def __len__(self) -> int:
        return len(self._checks)

    # ------------------------------------------------------------------ #
    # Execution                                                            #
    # ------------------------------------------------------------------ #

    def run(self, name: str) -> CheckResult:
        """Run a single check by name."""
        if name not in self._checks:
            raise CheckError(f"Unknown check: {name!r}")
        return self._checks[name]()

    def run_all(self) -> HealthReport:
        """Run all registered checks and return aggregate report."""
        report = HealthReport()
        for name, fn in self._checks.items():
            result = fn()
            report.results.append(result)
        report.finished_at = time.time()
        return report

    def run_parallel(self) -> HealthReport:
        """Run all checks in parallel using threads."""
        import threading
        report = HealthReport()
        results: list[CheckResult] = [None] * len(self._checks)  # type: ignore
        threads: list[threading.Thread] = []

        for i, (name, fn) in enumerate(self._checks.items()):
            def _run(idx=i, check=fn):
                results[idx] = check()
            t = threading.Thread(target=_run, daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=self._timeout + 1)

        report.results = [r for r in results if r is not None]
        report.finished_at = time.time()
        return report

    # ------------------------------------------------------------------ #
    # Check factories                                                      #
    # ------------------------------------------------------------------ #

    def _make_http_check(
        self, name: str, url: str, expected_status: int
    ) -> CheckFn:
        timeout = self._timeout

        def check() -> CheckResult:
            t0 = time.time()
            try:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    status = resp.status
                latency = (time.time() - t0) * 1000
                if status == expected_status:
                    return CheckResult(name=name, status=CheckStatus.UP,
                                       latency_ms=latency,
                                       details={"http_status": status})
                return CheckResult(name=name, status=CheckStatus.DOWN,
                                   latency_ms=latency,
                                   message=f"HTTP {status} (expected {expected_status})",
                                   details={"http_status": status})
            except urllib.error.HTTPError as exc:
                latency = (time.time() - t0) * 1000
                if exc.code == expected_status:
                    return CheckResult(name=name, status=CheckStatus.UP,
                                       latency_ms=latency,
                                       details={"http_status": exc.code})
                return CheckResult(name=name, status=CheckStatus.DOWN,
                                   latency_ms=latency,
                                   message=f"HTTP {exc.code}")
            except TimeoutError:
                return CheckResult(name=name, status=CheckStatus.TIMEOUT,
                                   latency_ms=(time.time() - t0) * 1000,
                                   message="connection timed out")
            except Exception as exc:  # noqa: BLE001
                return CheckResult(name=name, status=CheckStatus.DOWN,
                                   latency_ms=(time.time() - t0) * 1000,
                                   message=str(exc))
        return check

    def _make_tcp_check(self, name: str, host: str, port: int) -> CheckFn:
        timeout = self._timeout

        def check() -> CheckResult:
            t0 = time.time()
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    latency = (time.time() - t0) * 1000
                    return CheckResult(name=name, status=CheckStatus.UP,
                                       latency_ms=latency,
                                       details={"host": host, "port": port})
            except TimeoutError:
                return CheckResult(name=name, status=CheckStatus.TIMEOUT,
                                   latency_ms=(time.time() - t0) * 1000,
                                   message=f"tcp timeout connecting to {host}:{port}")
            except OSError as exc:
                return CheckResult(name=name, status=CheckStatus.DOWN,
                                   latency_ms=(time.time() - t0) * 1000,
                                   message=str(exc))
        return check

    # ------------------------------------------------------------------ #
    # Presets                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def with_defaults(cls, timeout: float = 3.0) -> "LivenessChecker":
        """Return checker with localhost common-service checks."""
        checker = cls(timeout=timeout)
        checker.add_tcp("postgres", "127.0.0.1", 5432)
        checker.add_tcp("redis", "127.0.0.1", 6379)
        checker.add_tcp("rabbitmq", "127.0.0.1", 5672)
        return checker
