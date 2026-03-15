"""Test runner for the TDD pipeline — Task 286.

Runs pytest as a subprocess and parses results into a structured
``TestRunResult``.

Usage::

    runner = TestRunner()
    result = runner.run("tests/unit/test_foo.py")
    if result.passed:
        print("GREEN")
    else:
        print(result.summary)
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 60  # seconds


@dataclass
class TestCase:
    """Result for a single test case."""

    nodeid: str
    outcome: str   # "passed" | "failed" | "error" | "skipped"
    message: str = ""


@dataclass
class TestRunResult:
    """Result of a pytest run."""

    passed: bool
    total: int = 0
    n_passed: int = 0
    n_failed: int = 0
    n_error: int = 0
    n_skipped: int = 0
    cases: list[TestCase] = field(default_factory=list)
    output: str = ""   # raw stderr+stdout for debugging
    error: str = ""    # error message if pytest couldn't run

    @property
    def summary(self) -> str:
        if self.error:
            return f"Test run error: {self.error}"
        status = "GREEN ✅" if self.passed else "RED ❌"
        parts = [f"{status} — {self.n_passed}/{self.total} passed"]
        if self.n_failed:
            parts.append(f"{self.n_failed} failed")
        if self.n_error:
            parts.append(f"{self.n_error} errors")
        if self.n_skipped:
            parts.append(f"{self.n_skipped} skipped")
        # Show first failing test output
        failing = [c for c in self.cases if c.outcome in ("failed", "error")]
        if failing:
            parts.append(f"\nFirst failure: {failing[0].nodeid}")
            if failing[0].message:
                parts.append(failing[0].message[:500])
        return " | ".join(parts[:3]) + ("\n" + "\n".join(parts[3:]) if len(parts) > 3 else "")


class TestRunner:
    """Runs pytest and returns structured results.

    Args:
        project_dir: Working directory for pytest. Defaults to cwd.
        timeout: Maximum seconds to wait for tests.
    """

    def __init__(
        self,
        project_dir: Path | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._project_dir = project_dir or Path.cwd()
        self._timeout = timeout

    def run(self, target: str = "", extra_args: list[str] | None = None) -> TestRunResult:
        """Run pytest on *target* (file/dir/nodeid) and return results.

        Uses ``--json-report`` when available, falls back to stdout parsing.
        """
        cmd = [sys.executable, "-m", "pytest", "--tb=short", "-q"]
        if target:
            cmd.append(target)
        if extra_args:
            cmd.extend(extra_args)

        # Try JSON report for structured output
        json_report_path = self._project_dir / ".lidco" / "_tdd_pytest_report.json"
        json_report_path.parent.mkdir(parents=True, exist_ok=True)
        cmd_json = cmd + [
            "--json-report",
            f"--json-report-file={json_report_path}",
        ]

        try:
            proc = subprocess.run(
                cmd_json,
                cwd=self._project_dir,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            if json_report_path.exists():
                return self._parse_json_report(json_report_path, proc.stdout + proc.stderr)
        except FileNotFoundError:
            pass  # pytest-json-report not installed
        except subprocess.TimeoutExpired:
            return TestRunResult(passed=False, error=f"Test run timed out after {self._timeout}s")
        except Exception as exc:
            logger.debug("JSON report failed: %s, falling back", exc)

        # Fallback: plain pytest
        try:
            proc = subprocess.run(
                cmd,
                cwd=self._project_dir,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            return self._parse_stdout(proc.stdout + proc.stderr, proc.returncode)
        except subprocess.TimeoutExpired:
            return TestRunResult(passed=False, error=f"Test run timed out after {self._timeout}s")
        except Exception as exc:
            return TestRunResult(passed=False, error=str(exc))

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_json_report(self, path: Path, raw_output: str) -> TestRunResult:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return self._parse_stdout(raw_output, returncode=1)

        summary = data.get("summary", {})
        cases: list[TestCase] = []
        for t in data.get("tests", []):
            outcome = t.get("outcome", "unknown")
            msg = ""
            if outcome in ("failed", "error"):
                call_data = t.get("call", {}) or t.get("setup", {}) or {}
                longrepr = call_data.get("longrepr", "")
                msg = str(longrepr)[:600] if longrepr else ""
            cases.append(TestCase(nodeid=t.get("nodeid", ""), outcome=outcome, message=msg))

        n_passed = summary.get("passed", 0)
        n_failed = summary.get("failed", 0)
        n_error = summary.get("error", 0)
        n_skipped = summary.get("skipped", 0)
        total = n_passed + n_failed + n_error + n_skipped

        return TestRunResult(
            passed=(n_failed == 0 and n_error == 0),
            total=total,
            n_passed=n_passed,
            n_failed=n_failed,
            n_error=n_error,
            n_skipped=n_skipped,
            cases=cases,
            output=raw_output[:2000],
        )

    def _parse_stdout(self, output: str, returncode: int) -> TestRunResult:
        """Parse pytest stdout for summary line."""
        import re
        # Match: "3 passed", "1 failed, 2 passed", etc.
        pattern = re.compile(
            r"(\d+) passed|(\d+) failed|(\d+) error|(\d+) skipped"
        )
        n_passed = n_failed = n_error = n_skipped = 0
        for m in pattern.finditer(output):
            if m.group(1):
                n_passed = int(m.group(1))
            elif m.group(2):
                n_failed = int(m.group(2))
            elif m.group(3):
                n_error = int(m.group(3))
            elif m.group(4):
                n_skipped = int(m.group(4))

        total = n_passed + n_failed + n_error + n_skipped
        passed = returncode == 0 and n_failed == 0 and n_error == 0

        # Extract FAILED lines as cases
        cases: list[TestCase] = []
        for line in output.splitlines():
            if line.startswith("FAILED "):
                nodeid = line[7:].split(" - ")[0].strip()
                msg = line.split(" - ", 1)[1] if " - " in line else ""
                cases.append(TestCase(nodeid=nodeid, outcome="failed", message=msg))

        return TestRunResult(
            passed=passed,
            total=total,
            n_passed=n_passed,
            n_failed=n_failed,
            n_error=n_error,
            n_skipped=n_skipped,
            cases=cases,
            output=output[:2000],
        )
