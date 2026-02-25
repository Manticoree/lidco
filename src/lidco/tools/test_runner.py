"""Pytest test runner tool with structured output."""

from __future__ import annotations

import asyncio
import re
from typing import Any, Callable

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class RunTestsTool(BaseTool):
    """Run pytest and return structured test results."""

    @property
    def name(self) -> str:
        return "run_tests"

    @property
    def description(self) -> str:
        return (
            "Run pytest and return structured results: pass/fail counts, "
            "failed test names, and optionally coverage summary."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="test_path",
                type="string",
                description="Path to test file, directory, or test ID. Empty = run all.",
                required=False,
                default="",
            ),
            ToolParameter(
                name="verbose",
                type="boolean",
                description="Show individual test names in output.",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="coverage",
                type="boolean",
                description="Include per-file coverage report (requires pytest-cov).",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Maximum seconds to wait for the test suite.",
                required=False,
                default=120,
            ),
            ToolParameter(
                name="stream_output",
                type="boolean",
                description=(
                    "Stream pytest output lines in real time via the progress "
                    "callback. Requires a progress callback to be set; falls "
                    "back to buffered mode when none is available."
                ),
                required=False,
                default=False,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, **kwargs: Any) -> ToolResult:
        test_path: str = kwargs.get("test_path", "")
        verbose: bool = bool(kwargs.get("verbose", False))
        coverage: bool = bool(kwargs.get("coverage", False))
        timeout: int = int(kwargs.get("timeout", 120))
        stream_output: bool = bool(kwargs.get("stream_output", False))

        cmd = ["python", "-m", "pytest"]
        if verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")
        if coverage:
            cmd += ["--cov", "--cov-report=term-missing"]
        if test_path:
            cmd.append(test_path)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            if stream_output and self._progress_callback is not None:
                stdout_text, stderr_text = await _stream_lines(
                    process, self._progress_callback, timeout
                )
            else:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
                stdout_text = stdout.decode("utf-8", errors="replace")
                stderr_text = stderr.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            return ToolResult(
                output="", success=False, error=f"Tests timed out after {timeout}s"
            )
        except FileNotFoundError:
            return ToolResult(
                output="", success=False, error="pytest not found — install it first."
            )

        passed, failed, errors, skipped = _parse_summary(stdout_text)
        failed_tests = _extract_failed_tests(stdout_text)

        summary_parts: list[str] = []
        if passed:
            summary_parts.append(f"{passed} passed")
        if failed:
            summary_parts.append(f"{failed} failed")
        if errors:
            summary_parts.append(f"{errors} error{'s' if errors > 1 else ''}")
        if skipped:
            summary_parts.append(f"{skipped} skipped")

        output_lines: list[str] = [
            f"Test results: {', '.join(summary_parts) if summary_parts else 'no tests collected'}"
        ]

        if failed_tests:
            output_lines.append(f"\nFailed tests ({len(failed_tests)}):")
            for t in failed_tests[:20]:
                output_lines.append(f"  FAILED {t}")
            if len(failed_tests) > 20:
                output_lines.append(f"  ... {len(failed_tests) - 20} more")

        if coverage:
            cov_section = _extract_coverage_summary(stdout_text)
            if cov_section:
                output_lines.append(f"\nCoverage:\n{cov_section}")

        if failed or errors:
            failure_section = _extract_failure_section(stdout_text)
            if failure_section:
                output_lines.append(f"\n{failure_section}")

        if stderr_text.strip():
            output_lines.append(f"\n[stderr]\n{stderr_text[:2000]}")

        output = "\n".join(output_lines)
        if len(output) > 15000:
            output = output[:12000] + "\n\n... (truncated)"

        return ToolResult(
            output=output,
            success=process.returncode == 0,
            error=(
                None
                if process.returncode == 0
                else f"Tests failed (exit code {process.returncode})"
            ),
            metadata={
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "skipped": skipped,
                "exit_code": process.returncode or 0,
                "failed_tests": failed_tests[:10],
            },
        )


async def _stream_lines(
    process: asyncio.subprocess.Process,
    callback: Callable[[str], None],
    timeout: int,
) -> tuple[str, str]:
    """Read *process* stdout line-by-line, calling *callback* for each line.

    Returns ``(stdout_text, stderr_text)`` once the process exits (or raises
    ``asyncio.TimeoutError`` if *timeout* seconds elapse before EOF).
    """
    lines: list[str] = []

    async def _read() -> None:
        assert process.stdout is not None
        while True:
            raw = await process.stdout.readline()
            if not raw:
                break
            text = raw.decode("utf-8", errors="replace")
            lines.append(text)
            callback(text.rstrip("\n"))

    await asyncio.wait_for(_read(), timeout=timeout)
    await process.wait()
    stderr_raw = b""
    if process.stderr is not None:
        stderr_raw = await process.stderr.read()
    return "".join(lines), stderr_raw.decode("utf-8", errors="replace")


def _parse_summary(output: str) -> tuple[int, int, int, int]:
    """Extract passed/failed/error/skipped counts from pytest summary line."""
    passed = failed = errors = skipped = 0
    for line in reversed(output.splitlines()):
        if any(kw in line for kw in ("passed", "failed", "error", "no tests")):
            m = re.search(r"(\d+) passed", line)
            if m:
                passed = int(m.group(1))
            m = re.search(r"(\d+) failed", line)
            if m:
                failed = int(m.group(1))
            m = re.search(r"(\d+) error", line)
            if m:
                errors = int(m.group(1))
            m = re.search(r"(\d+) skipped", line)
            if m:
                skipped = int(m.group(1))
            break
    return passed, failed, errors, skipped


def _extract_failed_tests(output: str) -> list[str]:
    """Extract FAILED test IDs from pytest output."""
    failed: list[str] = []
    for line in output.splitlines():
        if line.startswith("FAILED "):
            test_id = line[7:].split(" - ")[0].strip()
            failed.append(test_id)
    return failed


def _extract_coverage_summary(output: str) -> str:
    """Extract coverage table (Name / Stmts / Miss / Cover) from output."""
    lines = output.splitlines()
    in_cov = False
    cov_lines: list[str] = []
    for line in lines:
        if "Name" in line and "Stmts" in line and "Miss" in line:
            in_cov = True
        if in_cov:
            cov_lines.append(line)
            if line.startswith("TOTAL"):
                break
    return "\n".join(cov_lines[:30]) if cov_lines else ""


def _extract_failure_section(output: str) -> str:
    """Extract FAILURES and ERRORS sections from pytest output (up to 100 lines each)."""
    lines = output.splitlines()
    sections: list[str] = []

    for pattern in (r"=+ FAILURES? =+", r"=+ ERRORS? =+"):
        start = -1
        for i, line in enumerate(lines):
            if re.match(pattern, line):
                start = i
                break
        if start != -1:
            end = min(start + 100, len(lines))
            sections.append("\n".join(lines[start:end]))

    return "\n\n".join(sections)
