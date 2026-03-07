"""Multi-run pytest executor for flaky test detection.

Runs the test suite N times via subprocess, parses JSON output from
``pytest-json-report``, feeds outcomes into :class:`FlakeHistory`, and
returns a :class:`MultiRunResult` with detected flaky tests.

Usage::

    import asyncio
    from lidco.core.flake_runner import MultiRunConfig, run_tests_multi

    cfg = MultiRunConfig(test_paths=["tests/unit/"], runs=5)
    result = asyncio.run(run_tests_multi(cfg))
    for rec in result.flaky_tests:
        print(f"{rec.test_id}: {rec.flake_rate:.0%} flake rate over {rec.runs} runs")
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from typing import Any

from lidco.core.flake_detector import FlakeHistory, FlakeRecord, TestOutcome

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiRunConfig:
    """Configuration for a multi-run flake detection session.

    Attributes:
        test_paths:          Paths (files or directories) to pass to pytest.
        runs:                Number of times to run the test suite (default 3).
        timeout_per_run:     Maximum seconds allowed per pytest invocation (default 120).
        min_flake_rate:      Minimum flake rate to include in results (default 0.1 = 10%).
        min_runs_for_flake:  Minimum runs required before flagging a test (default 2).
        extra_pytest_args:   Additional arguments forwarded to pytest.
    """

    test_paths: list[str]
    runs: int = 3
    timeout_per_run: int = 120
    min_flake_rate: float = 0.1
    min_runs_for_flake: int = 2
    extra_pytest_args: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiRunResult:
    """Output of a multi-run flake detection session.

    Attributes:
        history:     Full :class:`FlakeHistory` across all runs.
        flaky_tests: Tests whose flake rate met the configured thresholds, sorted
                     by flake rate descending.
        total_runs:  Number of pytest invocations that completed (possibly < runs
                     if some were skipped due to errors).
        run_errors:  Human-readable error messages for failed invocations.
    """

    history: FlakeHistory
    flaky_tests: list[FlakeRecord]
    total_runs: int
    run_errors: list[str]


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def _parse_pytest_json(data: dict[str, Any]) -> list[TestOutcome]:
    """Parse a ``pytest-json-report`` JSON dict into :class:`TestOutcome` objects.

    Skipped tests are excluded.  ``error`` outcome is treated as a failure.

    Args:
        data: Parsed JSON dict from ``pytest --json-report --json-report-file=-``.

    Returns:
        A list of :class:`TestOutcome` objects (may be empty).
    """
    outcomes: list[TestOutcome] = []
    tests = data.get("tests")
    if not isinstance(tests, list):
        return outcomes

    for entry in tests:
        if not isinstance(entry, dict):
            continue
        outcome = entry.get("outcome", "")
        if outcome == "skipped":
            continue

        test_id: str = entry.get("nodeid", "unknown")
        passed: bool = outcome == "passed"

        # Duration — nested under "call" key by pytest-json-report
        call = entry.get("call") or {}
        duration_s: float = float(call.get("duration", 0.0)) if isinstance(call, dict) else 0.0

        # Error message — longrepr is a string or complex object
        error_msg: str | None = None
        if not passed:
            longrepr = entry.get("longrepr")
            if longrepr:
                if isinstance(longrepr, str):
                    # Keep first line only to stay compact
                    error_msg = longrepr.splitlines()[0][:200] if longrepr else None
                else:
                    error_msg = str(longrepr)[:200]

        outcomes.append(TestOutcome(
            test_id=test_id,
            passed=passed,
            duration_s=duration_s,
            error_msg=error_msg,
        ))

    return outcomes


# ---------------------------------------------------------------------------
# Multi-run executor
# ---------------------------------------------------------------------------


async def _run_pytest_once(
    test_paths: list[str],
    extra_args: tuple[str, ...],
    timeout: int,
) -> tuple[list[TestOutcome], str | None]:
    """Execute pytest once and return parsed outcomes plus optional error string.

    Uses ``--json-report --json-report-file=-`` so results arrive on stdout
    without touching the filesystem.
    """
    cmd = [
        sys.executable, "-m", "pytest",
        "--json-report", "--json-report-file=-",
        "-q",
        *extra_args,
        *test_paths,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=float(timeout)
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return [], f"Pytest run timed out after {timeout}s"

        raw = stdout.decode("utf-8", errors="replace").strip()
        if not raw:
            return [], f"No output from pytest (exit {proc.returncode})"

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return [], f"JSON parse error: {exc}"

        return _parse_pytest_json(data), None

    except OSError as exc:
        return [], f"Failed to launch pytest: {exc}"
    except Exception as exc:
        return [], f"Unexpected error: {exc}"


async def run_tests_multi(cfg: MultiRunConfig) -> MultiRunResult:
    """Run the test suite multiple times and detect flaky tests.

    Args:
        cfg: A :class:`MultiRunConfig` describing paths, run count, and thresholds.

    Returns:
        A :class:`MultiRunResult` with the accumulated :class:`FlakeHistory`
        and the list of flaky tests sorted by flake rate descending.
    """
    history = FlakeHistory()
    run_errors: list[str] = []
    completed_runs = 0

    for run_idx in range(cfg.runs):
        logger.debug("Flake detection run %d/%d", run_idx + 1, cfg.runs)
        outcomes, error = await _run_pytest_once(
            cfg.test_paths,
            cfg.extra_pytest_args,
            cfg.timeout_per_run,
        )
        if error:
            run_errors.append(f"Run {run_idx + 1}: {error}")
            logger.warning("Flake run %d failed: %s", run_idx + 1, error)
            continue

        for outcome in outcomes:
            history.record_outcome(outcome)
        completed_runs += 1

    flaky = history.get_flaky_tests(
        min_flake_rate=cfg.min_flake_rate,
        min_runs=cfg.min_runs_for_flake,
    )

    return MultiRunResult(
        history=history,
        flaky_tests=flaky,
        total_runs=completed_runs,
        run_errors=run_errors,
    )
