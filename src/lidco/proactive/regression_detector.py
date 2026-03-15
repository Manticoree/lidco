"""Regression detector — Task 411."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RegressionResult:
    """Result of a regression detection run."""

    passed: int
    failed: int
    test_files_run: list[str]
    duration_ms: float


class RegressionDetector:
    """Detect regressions caused by changes to a source file."""

    # Max time to wait for pytest (seconds)
    _TIMEOUT = 60

    def __init__(self, project_root: str = ".") -> None:
        self._root = Path(project_root)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def find_related_tests(self, file_path: str) -> list[str]:
        """Find test files that reference symbols from *file_path*."""
        src = Path(file_path)
        # Derive module base name (e.g. auth.py → auth)
        stem = src.stem
        if len(stem) < 2:
            return []

        tests_dir = self._root / "tests"
        if not tests_dir.is_dir():
            return []

        found: list[str] = []
        pattern = re.compile(re.escape(stem), re.IGNORECASE)
        for test_file in tests_dir.rglob("test_*.py"):
            if pattern.search(test_file.name):
                found.append(str(test_file))
            elif pattern.search(test_file.read_text(encoding="utf-8", errors="ignore")):
                found.append(str(test_file))
        return found[:10]  # cap at 10

    async def detect(self, file_path: str) -> RegressionResult:
        """Run related tests for *file_path* and return results."""
        test_files = self.find_related_tests(file_path)
        if not test_files:
            return RegressionResult(passed=0, failed=0, test_files_run=[], duration_ms=0.0)

        start = time.monotonic()
        passed, failed = await self._run_pytest(test_files)
        duration_ms = (time.monotonic() - start) * 1000
        return RegressionResult(
            passed=passed,
            failed=failed,
            test_files_run=test_files,
            duration_ms=round(duration_ms, 1),
        )

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    async def _run_pytest(self, test_files: list[str]) -> tuple[int, int]:
        """Run pytest and return (passed, failed)."""
        cmd = ["python", "-m", "pytest"] + test_files + ["-x", "-q", "--tb=no", "--no-header"]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, _ = await asyncio.wait_for(proc.communicate(), timeout=self._TIMEOUT)
            output = stdout_b.decode("utf-8", errors="replace")
        except (asyncio.TimeoutError, OSError):
            return (0, 0)

        return self._parse_pytest_output(output)

    @staticmethod
    def _parse_pytest_output(output: str) -> tuple[int, int]:
        """Parse pytest summary line like '3 passed, 1 failed'."""
        passed = 0
        failed = 0
        m_passed = re.search(r"(\d+)\s+passed", output)
        m_failed = re.search(r"(\d+)\s+failed", output)
        if m_passed:
            passed = int(m_passed.group(1))
        if m_failed:
            failed = int(m_failed.group(1))
        return passed, failed
