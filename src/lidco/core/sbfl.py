"""Ochiai SBFL (Spectrum-Based Fault Localization) for suspiciously failing lines.

Implements the Ochiai formula (EMSE 2024 — best formula on 135 Python bugs) to rank
source lines by their likelihood of being the fault location.

Formula::

    ochiai(ef, ep, nf) = ef / sqrt(nf * (ef + ep))

Where:
- ef = number of FAILING tests that executed this line
- ep = number of PASSING tests that executed this line
- nf = total number of FAILING tests

Reference: Abreu, Zoeteweij & van Gemund (2009); validated on Python bugs (EMSE 2024).

Usage::

    from lidco.core.sbfl import collect_sbfl_spectra, compute_sbfl, format_suspicious_lines

    spectra, results = await collect_sbfl_spectra(test_paths, target_file, project_dir)
    smap = compute_sbfl(spectra, results, "src/lidco/core/session.py")
    print(format_suspicious_lines(smap))
"""

from __future__ import annotations

import asyncio
import logging
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SuspiciousnessScore:
    """Ochiai suspiciousness for a single source line.

    Attributes:
        line:        1-based line number.
        score:       Ochiai coefficient in [0.0, 1.0].
        failed_hits: Number of failing tests that executed this line.
        passed_hits: Number of passing tests that executed this line.
    """

    line: int
    score: float
    failed_hits: int
    passed_hits: int


@dataclass(frozen=True)
class SuspiciousnessMap:
    """Ochiai suspiciousness scores for all lines of a single file.

    Attributes:
        file_path:     Source file path (as passed to :func:`compute_sbfl`).
        scores:        Line scores sorted by suspiciousness descending.
        total_failing: Total number of failing tests used for this analysis.
        total_passing: Total number of passing tests used.
    """

    file_path: str
    scores: list[SuspiciousnessScore]
    total_failing: int
    total_passing: int


# ---------------------------------------------------------------------------
# Ochiai formula
# ---------------------------------------------------------------------------


def ochiai(ef: int, ep: int, total_failed: int) -> float:
    """Compute the Ochiai suspiciousness coefficient.

    Args:
        ef:           Number of failing tests that execute the element.
        ep:           Number of passing tests that execute the element.
        total_failed: Total number of failing tests in the test suite.

    Returns:
        Float in ``[0.0, 1.0]``.  Returns ``0.0`` when the denominator is zero
        (element never executed by failing tests, or no failing tests at all).
    """
    denom = math.sqrt(total_failed * (ef + ep))
    if denom == 0.0:
        return 0.0
    return ef / denom


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------


def compute_sbfl(
    spectra: dict[str, set[int]],
    results: dict[str, bool],
    file_path: str,
) -> SuspiciousnessMap:
    """Compute Ochiai SBFL scores for *file_path*.

    Args:
        spectra:   ``{test_id: set_of_executed_lines}`` — coverage per test,
                   already filtered to the target file (i.e., the sets contain
                   lines from *file_path* only).
        results:   ``{test_id: passed}`` — True = passed, False = failed.
        file_path: The source file being analysed.

    Returns:
        A :class:`SuspiciousnessMap` with scores sorted by suspiciousness
        descending (most suspicious first).
    """
    failing_tests = {tid for tid, passed in results.items() if not passed}
    passing_tests = {tid for tid, passed in results.items() if passed}
    total_failing = len(failing_tests)
    total_passing = len(passing_tests)

    # Collect all executed lines across all tests
    all_lines: set[int] = set()
    for lines in spectra.values():
        all_lines.update(lines)

    scores: list[SuspiciousnessScore] = []
    for line in sorted(all_lines):
        ef = sum(1 for tid in failing_tests if line in spectra.get(tid, set()))
        ep = sum(1 for tid in passing_tests if line in spectra.get(tid, set()))
        s = ochiai(ef, ep, total_failing)
        scores.append(SuspiciousnessScore(line=line, score=s, failed_hits=ef, passed_hits=ep))

    scores.sort(key=lambda x: x.score, reverse=True)
    return SuspiciousnessMap(
        file_path=file_path,
        scores=scores,
        total_failing=total_failing,
        total_passing=total_passing,
    )


# ---------------------------------------------------------------------------
# Coverage data reader
# ---------------------------------------------------------------------------


def read_coverage_contexts(
    coverage_file: Path,
    target_file: str,
) -> dict[str, set[int]]:
    """Read per-test line coverage from a ``.coverage`` binary file.

    Requires ``coverage.py ≥ 5.0`` with ``--cov-context=test`` to be present.
    Returns a ``{test_id: set_of_lines}`` mapping for *target_file* only.

    Returns ``{}`` on any error (file not found, no contexts, API mismatch).
    """
    try:
        from coverage import CoverageData  # type: ignore[import-untyped]

        cdata = CoverageData(str(coverage_file))
        cdata.read()
        contexts = cdata.measured_contexts()
        if not contexts:
            return {}

        spectra: dict[str, set[int]] = {}
        norm_target = target_file.replace("\\", "/")

        for ctx in contexts:
            if not ctx:
                continue
            try:
                cdata.set_query_contexts([ctx])
                for fname in cdata.measured_files():
                    norm_fname = fname.replace("\\", "/")
                    if norm_target in norm_fname or norm_fname.endswith(norm_target):
                        lines = cdata.lines(fname) or []
                        spectra[ctx] = set(lines)
                        break
            except Exception as exc:
                logger.debug("SBFL context read failed for %s: %s", ctx, exc)
                continue

        return spectra
    except ImportError:
        logger.debug("coverage.py not installed — SBFL unavailable")
        return {}
    except Exception as exc:
        logger.debug("read_coverage_contexts failed: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Spectra collector (async subprocess)
# ---------------------------------------------------------------------------


async def collect_sbfl_spectra(
    test_paths: list[str],
    target_file: str,
    project_dir: Path,
    timeout_s: float = 60.0,
) -> tuple[dict[str, set[int]], dict[str, bool]]:
    """Collect per-test coverage spectra by running pytest with context tracking.

    Runs::

        pytest <test_paths> --cov=. --cov-context=test --json-report
            --json-report-file=.lidco/sbfl_report.json -q --tb=no

    Then reads the ``.coverage`` binary for per-test line data and
    ``.lidco/sbfl_report.json`` for pass/fail results.

    Returns:
        A tuple ``(spectra, results)`` where:
        - *spectra*: ``{test_id: set_of_lines}`` for *target_file*
        - *results*: ``{test_id: passed}``

    Returns ``({}, {})`` on any error (timeout, missing tools, etc.).
    """
    coverage_file = project_dir / ".coverage"
    report_file = project_dir / ".lidco" / "sbfl_report.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python", "-m", "pytest",
        *test_paths,
        "--cov=.",
        "--cov-context=test",
        "--json-report",
        f"--json-report-file={report_file}",
        "-q",
        "--tb=no",
        "--no-header",
    ]

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(project_dir),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            ),
            timeout=5.0,
        )
        await asyncio.wait_for(proc.wait(), timeout=timeout_s)
    except asyncio.TimeoutError:
        logger.debug("SBFL spectra collection timed out after %ss", timeout_s)
        return {}, {}
    except Exception as exc:
        logger.debug("SBFL spectra collection failed: %s", exc)
        return {}, {}

    # Read per-test results from JSON report
    results: dict[str, bool] = {}
    try:
        import json
        if report_file.exists():
            data = json.loads(report_file.read_text(encoding="utf-8"))
            for test in data.get("tests", []):
                tid = test.get("nodeid", "")
                outcome = test.get("outcome", "failed")
                if tid:
                    results[tid] = outcome == "passed"
    except Exception as exc:
        logger.debug("SBFL report parse failed: %s", exc)

    # Read per-test coverage spectra
    spectra: dict[str, set[int]] = {}
    if coverage_file.exists():
        spectra = read_coverage_contexts(coverage_file, target_file)

    return spectra, results


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def format_suspicious_lines(smap: SuspiciousnessMap, top_n: int = 10) -> str:
    """Format *smap* as a Markdown section for agent context injection.

    Returns ``""`` when there are no suspicious lines (all scores zero or
    empty map).

    Example output::

        ## Suspicious Lines (Ochiai)
        File: src/lidco/core/session.py (3 failing / 12 passing tests)

        | Line | Score | Fail-hits | Pass-hits |
        |------|-------|-----------|-----------|
        | 142  | 0.87  | 3         | 1         |
        | 98   | 0.71  | 2         | 0         |
    """
    relevant = [s for s in smap.scores if s.score > 0.0]
    if not relevant:
        return ""

    top = relevant[:top_n]
    lines: list[str] = [
        "## Suspicious Lines (Ochiai)\n",
        f"File: `{smap.file_path}` "
        f"({smap.total_failing} failing / {smap.total_passing} passing tests)\n",
        "| Line | Score | Fail-hits | Pass-hits |",
        "|------|-------|-----------|-----------|",
    ]
    for s in top:
        lines.append(
            f"| {s.line} | {s.score:.2f} | {s.failed_hits} | {s.passed_hits} |"
        )
    return "\n".join(lines)
