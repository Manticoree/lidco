"""Visual regression test runner — capture, compare, report (Cursor cloud agent parity)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VisualTestCase:
    name: str
    url: str
    actions: list[dict[str, Any]] = field(default_factory=list)  # pre-screenshot actions
    selector: str = ""    # optional: screenshot specific element
    tags: list[str] = field(default_factory=list)


@dataclass
class VisualTestResult:
    test: VisualTestCase
    passed: bool
    baseline_hash: str = ""
    current_hash: str = ""
    diff_pixels: int = -1   # -1 = not computed
    error: str = ""

    @property
    def is_new_baseline(self) -> bool:
        return self.baseline_hash == "" and self.passed


@dataclass
class VisualSuiteResult:
    results: list[VisualTestResult]
    passed: int
    failed: int
    new_baselines: int

    def format_report(self) -> str:
        lines = [f"Visual Test Suite: {self.passed} passed, {self.failed} failed, {self.new_baselines} new baselines"]
        for r in self.results:
            icon = "+" if r.passed else "-"
            tag = " [NEW]" if r.is_new_baseline else ""
            lines.append(f"  [{icon}] {r.test.name}{tag}")
            if r.error:
                lines.append(f"       Error: {r.error}")
        return "\n".join(lines)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


class VisualTestRunner:
    """Run visual regression tests by comparing screenshots to baselines.

    Baselines are stored as PNG files in a directory.
    Without Playwright, operates in dry-run mode.
    """

    def __init__(self, baseline_dir: str | Path = ".lidco/visual_baselines") -> None:
        self.baseline_dir = Path(baseline_dir)

    def _baseline_path(self, test_name: str) -> Path:
        return self.baseline_dir / f"{test_name}.png"

    def _load_baseline_hash(self, test_name: str) -> str:
        p = self._baseline_path(test_name)
        if not p.exists():
            return ""
        return _hash_bytes(p.read_bytes())

    def _save_baseline(self, test_name: str, data: bytes) -> None:
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self._baseline_path(test_name).write_bytes(data)

    def run_test(self, test: VisualTestCase, screenshot_bytes: bytes) -> VisualTestResult:
        """Compare screenshot to baseline. Creates baseline if absent."""
        current_hash = _hash_bytes(screenshot_bytes)
        baseline_hash = self._load_baseline_hash(test.name)

        if not baseline_hash:
            # First run — save as baseline
            self._save_baseline(test.name, screenshot_bytes)
            return VisualTestResult(
                test=test, passed=True,
                baseline_hash="", current_hash=current_hash,
            )

        passed = current_hash == baseline_hash
        return VisualTestResult(
            test=test, passed=passed,
            baseline_hash=baseline_hash, current_hash=current_hash,
        )

    def update_baseline(self, test_name: str, screenshot_bytes: bytes) -> None:
        """Explicitly update baseline for a test."""
        self._save_baseline(test_name, screenshot_bytes)

    def run_suite(self, tests: list[tuple[VisualTestCase, bytes]]) -> VisualSuiteResult:
        """Run multiple tests. Input: list of (test_case, screenshot_bytes)."""
        results: list[VisualTestResult] = []
        for test, data in tests:
            results.append(self.run_test(test, data))
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)
        new_baselines = sum(1 for r in results if r.is_new_baseline)
        return VisualSuiteResult(results=results, passed=passed, failed=failed, new_baselines=new_baselines)

    def list_baselines(self) -> list[str]:
        if not self.baseline_dir.exists():
            return []
        return [p.stem for p in self.baseline_dir.glob("*.png")]
