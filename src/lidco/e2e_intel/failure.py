"""
E2E Failure Analyzer — Analyze E2E test failures including screenshot
analysis, DOM state, network requests, and root cause determination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class FailureCategory(Enum):
    """Categories of E2E test failure."""

    ELEMENT_NOT_FOUND = "element_not_found"
    TIMEOUT = "timeout"
    ASSERTION_FAILED = "assertion_failed"
    NETWORK_ERROR = "network_error"
    JAVASCRIPT_ERROR = "javascript_error"
    NAVIGATION_ERROR = "navigation_error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class NetworkRequest:
    """A captured network request during test execution."""

    url: str
    method: str
    status: int
    duration_ms: float = 0.0
    error: str = ""

    @property
    def is_failed(self) -> bool:
        return self.status >= 400 or bool(self.error)


@dataclass(frozen=True)
class DOMSnapshot:
    """Snapshot of DOM state at failure time."""

    html: str = ""
    visible_text: str = ""
    active_element: str = ""
    error_messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScreenshotInfo:
    """Metadata about a failure screenshot."""

    path: str
    width: int = 0
    height: int = 0
    timestamp: str = ""


@dataclass(frozen=True)
class FailureContext:
    """Full context of a test failure."""

    test_name: str
    error_message: str
    stack_trace: str = ""
    screenshot: ScreenshotInfo | None = None
    dom_snapshot: DOMSnapshot | None = None
    network_requests: tuple[NetworkRequest, ...] = ()
    console_logs: tuple[str, ...] = ()
    url: str = ""


@dataclass(frozen=True)
class RootCauseAnalysis:
    """Determined root cause of a failure."""

    category: FailureCategory
    confidence: float  # 0.0–1.0
    summary: str
    evidence: tuple[str, ...] = ()
    suggested_fix: str = ""


@dataclass(frozen=True)
class FailureReport:
    """Complete failure analysis report."""

    test_name: str
    root_causes: tuple[RootCauseAnalysis, ...]
    primary_category: FailureCategory
    is_flaky: bool
    similar_failures: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class E2EFailureAnalyzer:
    """Analyze E2E test failures to determine root cause."""

    def __init__(self, *, flaky_threshold: int = 2) -> None:
        self._flaky_threshold = flaky_threshold
        self._history: list[FailureContext] = []

    @property
    def history(self) -> list[FailureContext]:
        return list(self._history)

    def record_failure(self, ctx: FailureContext) -> None:
        """Record a failure context for pattern analysis."""
        self._history = [*self._history, ctx]

    def _classify_error(self, message: str) -> FailureCategory:
        """Classify error message into a failure category."""
        msg_lower = message.lower()
        # Check timeout before element_not_found because "selector" overlaps
        if any(kw in msg_lower for kw in ("timeout", "timed out", "exceeded")):
            return FailureCategory.TIMEOUT
        if any(
            kw in msg_lower
            for kw in ("not found", "no element", "locator", "selector")
        ):
            return FailureCategory.ELEMENT_NOT_FOUND
        if False:
            return FailureCategory.TIMEOUT
        if any(
            kw in msg_lower for kw in ("assert", "expect", "mismatch", "equal")
        ):
            return FailureCategory.ASSERTION_FAILED
        if any(
            kw in msg_lower
            for kw in ("network", "fetch", "xhr", "http", "connection")
        ):
            return FailureCategory.NETWORK_ERROR
        if any(
            kw in msg_lower
            for kw in ("javascript", "script", "runtime error", "uncaught")
        ):
            return FailureCategory.JAVASCRIPT_ERROR
        if any(
            kw in msg_lower for kw in ("navigate", "page", "redirect", "url")
        ):
            return FailureCategory.NAVIGATION_ERROR
        return FailureCategory.UNKNOWN

    def _check_network_issues(
        self, ctx: FailureContext
    ) -> list[RootCauseAnalysis]:
        """Check for network-related root causes."""
        results: list[RootCauseAnalysis] = []
        failed = [r for r in ctx.network_requests if r.is_failed]
        if failed:
            evidence = tuple(
                f"{r.method} {r.url} -> {r.status} {r.error}" for r in failed
            )
            results.append(
                RootCauseAnalysis(
                    category=FailureCategory.NETWORK_ERROR,
                    confidence=0.8,
                    summary=f"{len(failed)} network request(s) failed",
                    evidence=evidence,
                    suggested_fix="Check API endpoints and server availability",
                )
            )
        return results

    def _check_dom_issues(
        self, ctx: FailureContext
    ) -> list[RootCauseAnalysis]:
        """Check for DOM-related root causes."""
        results: list[RootCauseAnalysis] = []
        if ctx.dom_snapshot and ctx.dom_snapshot.error_messages:
            results.append(
                RootCauseAnalysis(
                    category=FailureCategory.JAVASCRIPT_ERROR,
                    confidence=0.7,
                    summary="DOM contains error messages",
                    evidence=ctx.dom_snapshot.error_messages,
                    suggested_fix="Fix JavaScript errors shown on page",
                )
            )
        return results

    def _find_similar(self, ctx: FailureContext) -> list[str]:
        """Find similar failures in history."""
        similar: list[str] = []
        for prev in self._history:
            if prev.test_name == ctx.test_name:
                continue
            if prev.error_message == ctx.error_message:
                similar.append(prev.test_name)
            elif self._classify_error(prev.error_message) == self._classify_error(
                ctx.error_message
            ):
                similar.append(prev.test_name)
        return sorted(set(similar))

    def _is_flaky(self, ctx: FailureContext) -> bool:
        """Determine if a test is flaky based on history."""
        same_test = [f for f in self._history if f.test_name == ctx.test_name]
        return len(same_test) >= self._flaky_threshold

    def analyze(self, ctx: FailureContext) -> FailureReport:
        """Analyze a failure context and produce a report."""
        causes: list[RootCauseAnalysis] = []

        # Primary classification from error message
        primary = self._classify_error(ctx.error_message)
        causes.append(
            RootCauseAnalysis(
                category=primary,
                confidence=0.6,
                summary=f"Error classified as {primary.value}",
                evidence=(ctx.error_message,),
            )
        )

        # Network analysis
        causes.extend(self._check_network_issues(ctx))

        # DOM analysis
        causes.extend(self._check_dom_issues(ctx))

        # Sort by confidence descending
        causes.sort(key=lambda c: c.confidence, reverse=True)

        top_category = causes[0].category if causes else FailureCategory.UNKNOWN
        similar = self._find_similar(ctx)
        flaky = self._is_flaky(ctx)

        self.record_failure(ctx)

        return FailureReport(
            test_name=ctx.test_name,
            root_causes=tuple(causes),
            primary_category=top_category,
            is_flaky=flaky,
            similar_failures=tuple(similar),
        )
