"""CoverageGuard tool — run coverage and report uncovered lines/branches.

Executes ``python -m pytest --cov=<path> --cov-report=json`` (or reads an
existing ``.lidco/coverage.json``), then surfaces coverage gaps for the
specified file (or all files below a threshold) in a compact Markdown report.

Tool name: ``coverage_guard``
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class CoverageGuardTool(BaseTool):
    """Measure test coverage and surface uncovered lines/branches.

    Runs ``pytest --cov`` to generate a JSON coverage report, then identifies
    files with gaps (missing lines or branches) and returns a ranked Markdown
    summary.  If a ``file_path`` is specified, only that file is reported.
    """

    @property
    def name(self) -> str:
        return "coverage_guard"

    @property
    def description(self) -> str:
        return (
            "Measure test coverage and report uncovered lines and branches. "
            "Runs pytest with coverage collection, parses the JSON report, and "
            "returns files below the coverage threshold ranked by gap severity."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="file_path",
                type="string",
                description=(
                    "Source file to analyse (e.g. 'src/lidco/core/session.py'). "
                    "When omitted all files below the threshold are reported."
                ),
                required=False,
                default="",
            ),
            ToolParameter(
                name="threshold",
                type="number",
                description=(
                    "Coverage percentage below which a file is flagged (default 80.0)."
                ),
                required=False,
                default=80.0,
            ),
            ToolParameter(
                name="test_paths",
                type="string",
                description=(
                    "Space-separated pytest paths to collect coverage from "
                    "(e.g. 'tests/'). Defaults to 'tests/'."
                ),
                required=False,
                default="tests/",
            ),
            ToolParameter(
                name="use_existing",
                type="boolean",
                description=(
                    "When true, read the existing .lidco/coverage.json instead of "
                    "running pytest again (faster but may be stale). Default false."
                ),
                required=False,
                default=False,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(self, **kwargs: Any) -> ToolResult:
        from lidco.core.coverage_gap import (
            CoverageGap,
            find_gaps_for_file,
            format_coverage_gaps,
            parse_coverage_json,
        )

        file_path: str = str(kwargs.get("file_path") or "").strip()
        threshold: float = float(kwargs.get("threshold") or 80.0)
        test_paths_raw: str = str(kwargs.get("test_paths") or "tests/").strip()
        use_existing: bool = bool(kwargs.get("use_existing", False))

        test_paths = [p for p in test_paths_raw.split() if p]
        if not test_paths:
            test_paths = ["tests/"]

        project_dir = Path(".").resolve()
        json_out = project_dir / ".lidco" / "coverage.json"

        # Optionally run pytest to regenerate coverage
        if not use_existing:
            run_error = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: _run_pytest_coverage(project_dir, test_paths, json_out),
            )
            if run_error:
                return ToolResult(
                    output=f"pytest --cov failed:\n\n{run_error}",
                    success=False,
                    error=run_error,
                    metadata={},
                )

        if not json_out.exists():
            return ToolResult(
                output=(
                    "No coverage data found. Run `pytest --cov` first or pass "
                    "`use_existing=false` to generate it automatically."
                ),
                success=False,
                error="coverage.json not found",
                metadata={},
            )

        try:
            raw = json.loads(json_out.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ToolResult(
                output=f"Cannot read coverage.json: {exc}",
                success=False,
                error=str(exc),
                metadata={},
            )

        coverage_map = parse_coverage_json(raw)

        if file_path:
            gap = find_gaps_for_file(file_path, coverage_map)
            gaps: list[CoverageGap] = [gap] if gap else []
        else:
            gaps = [
                CoverageGap(
                    file_path=info.file_path,
                    missing_lines=info.missing_lines,
                    missing_branches=info.missing_branches,
                    coverage_pct=info.coverage_pct,
                )
                for info in coverage_map.values()
                if info.coverage_pct < threshold
                and (info.missing_lines or info.missing_branches)
            ]

        report = format_coverage_gaps(gaps)
        has_gaps = len(gaps) > 0

        return ToolResult(
            output=report,
            success=not has_gaps,
            metadata={
                "total_files": len(coverage_map),
                "gap_files": len(gaps),
                "threshold": threshold,
            },
        )


# ---------------------------------------------------------------------------
# Subprocess helper (runs off the event loop)
# ---------------------------------------------------------------------------


def _run_pytest_coverage(
    project_dir: Path,
    test_paths: list[str],
    json_out: Path,
) -> str | None:
    """Run pytest with coverage collection.

    Returns an error message string on failure, or ``None`` on success.
    """
    json_out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "python",
        "-m",
        "pytest",
        "--tb=no",
        "-q",
        "--cov=src",
        f"--cov-report=json:{json_out}",
        *test_paths,
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if result.returncode not in (0, 1):  # 1 = tests failed (still valid cov)
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            return (stderr or stdout)[:2000] or "pytest exited with non-zero status"
        return None
    except subprocess.TimeoutExpired:
        return "pytest --cov timed out (120s)"
    except (FileNotFoundError, OSError) as exc:
        return f"Failed to run pytest: {exc}"
