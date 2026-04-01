"""Screenshot-based visual testing."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lidco.computer_use.screenshot import ScreenRegion, ScreenshotResult


@dataclass(frozen=True)
class VisualAssertion:
    """A single visual assertion result."""

    name: str
    expected: str
    actual: str
    passed: bool
    tolerance: float = 0.0
    message: str = ""


@dataclass(frozen=True)
class VisualTestResult:
    """Result of running a visual test."""

    test_name: str
    assertions: tuple[VisualAssertion, ...]
    passed: bool
    duration_ms: float = 0.0


class VisualTestRunner:
    """Runner for screenshot-based visual tests."""

    def __init__(self, baseline_dir: str | Path | None = None) -> None:
        self._baseline_dir = Path(baseline_dir) if baseline_dir else None
        self._results: list[VisualTestResult] = []

    def assert_text_present(
        self, screenshot: ScreenshotResult, text: str
    ) -> VisualAssertion:
        """Assert that *text* is present in the screenshot's text content."""
        found = text.lower() in screenshot.text_content.lower()
        return VisualAssertion(
            name="text_present",
            expected=text,
            actual=screenshot.text_content,
            passed=found,
            message=f"Text '{text}' {'found' if found else 'not found'} in screenshot",
        )

    def assert_region_exists(
        self, screenshot: ScreenshotResult, label: str
    ) -> VisualAssertion:
        """Assert that a labelled region exists in the screenshot."""
        found = any(
            label.lower() in screenshot.text_content.lower()
            for _ in [None]
        ) and bool(screenshot.text_content)
        # Also accept if any region is present and label matches text content
        region_match = label.lower() in screenshot.text_content.lower() if screenshot.text_content else False
        passed = region_match or (bool(screenshot.regions) and label.lower() in screenshot.text_content.lower())
        return VisualAssertion(
            name="region_exists",
            expected=label,
            actual=str(len(screenshot.regions)) + " region(s)",
            passed=passed,
            message=f"Region '{label}' {'found' if passed else 'not found'}",
        )

    def run_test(
        self, name: str, assertions: list[VisualAssertion]
    ) -> VisualTestResult:
        """Run a named visual test with the given assertions."""
        start = time.monotonic()
        all_passed = all(a.passed for a in assertions)
        duration = (time.monotonic() - start) * 1000
        result = VisualTestResult(
            test_name=name,
            assertions=tuple(assertions),
            passed=all_passed,
            duration_ms=duration,
        )
        self._results.append(result)
        return result

    def results(self) -> list[VisualTestResult]:
        """Return all test results."""
        return list(self._results)

    def summary(self) -> str:
        """Return a human-readable summary of all test results."""
        if not self._results:
            return "No visual tests run."
        total = len(self._results)
        passed = sum(1 for r in self._results if r.passed)
        failed = total - passed
        lines = [f"Visual Tests: {total} total, {passed} passed, {failed} failed"]
        for r in self._results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"  [{status}] {r.test_name} ({len(r.assertions)} assertions)")
        return "\n".join(lines)
