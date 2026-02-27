"""ProfilerTool — run a Python script under cProfile and return hotspot summary."""

from __future__ import annotations

import asyncio
import io
import logging
import pstats
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

from lidco.tools.base import BaseTool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)

_MAX_OUTPUT_CHARS = 4000


class ProfilerTool(BaseTool):
    """Run a Python script with cProfile and return the top cumulative hotspots.

    Schema::

        run_profiler(
            script: str,              # path to .py file, or inline code snippet
            args: str = "",           # extra CLI args for the script
            sort_by: str = "cumulative",  # sort column
            top_n: int = 20,          # number of rows to return
        ) -> ToolResult
    """

    @property
    def name(self) -> str:
        return "run_profiler"

    @property
    def description(self) -> str:
        return (
            "Profile a Python script with cProfile. "
            "Returns top-N cumulative hotspots (file, lineno, function, ncalls, cumtime)."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="script",
                type="string",
                description="Path to a .py file or short inline Python code to profile.",
            ),
            ToolParameter(
                name="args",
                type="string",
                description="Extra command-line arguments passed to the script.",
                required=False,
                default="",
            ),
            ToolParameter(
                name="sort_by",
                type="string",
                description="Sort key: 'cumulative' (default), 'tottime', or 'calls'.",
                required=False,
                default="cumulative",
            ),
            ToolParameter(
                name="top_n",
                type="integer",
                description="How many rows to include in the output (default 20).",
                required=False,
                default=20,
            ),
            ToolParameter(
                name="stream_output",
                type="boolean",
                description=(
                    "Stream the profiled script's stdout lines in real time via "
                    "the progress callback. Profile stats are still returned "
                    "in the final ToolResult."
                ),
                required=False,
                default=False,
            ),
        ]

    async def _run(  # type: ignore[override]
        self,
        script: str,
        args: str = "",
        sort_by: str = "cumulative",
        top_n: int = 20,
        stream_output: bool = False,
    ) -> ToolResult:
        script_path = Path(script)
        use_temp = False

        if not script_path.exists():
            # Treat as inline code
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            )
            tmp.write(script)
            tmp.close()
            script_path = Path(tmp.name)
            use_temp = True

        stats_file: str | None = None
        try:
            stats_file = tempfile.mktemp(suffix=".prof")
            cmd = [
                sys.executable, "-m", "cProfile",
                "-o", stats_file,
                str(script_path),
            ] + (args.split() if args.strip() else [])

            returncode: int
            stderr_str: str

            if stream_output and self._progress_callback is not None:
                returncode, stderr_str = await _run_async_streaming(
                    cmd, self._progress_callback
                )
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                )
                returncode = result.returncode
                stderr_str = result.stderr

            try:
                buf = io.StringIO()
                stats = pstats.Stats(stats_file, stream=buf)
                stats.sort_stats(sort_by)
                stats.print_stats(top_n)
                profile_output = buf.getvalue()
            except Exception as e:
                profile_output = f"(Could not parse profile stats: {e})"

            stderr_hint = ""
            if stderr_str.strip():
                stderr_hint = f"\n\nStderr:\n{stderr_str[:500]}"

            output = f"## cProfile — top {top_n} by {sort_by}\n\n{profile_output}{stderr_hint}"
            if len(output) > _MAX_OUTPUT_CHARS:
                output = output[:_MAX_OUTPUT_CHARS] + "\n... (truncated)"

            return ToolResult(
                success=returncode == 0 or bool(profile_output.strip()),
                output=output,
                metadata={"returncode": returncode, "sort_by": sort_by},
            )

        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="Profiler timed out (60s limit).")
        except asyncio.TimeoutError:
            return ToolResult(success=False, output="Profiler timed out (60s limit).")
        except Exception as exc:
            logger.warning("ProfilerTool error: %s", exc)
            return ToolResult(success=False, output=f"Profiler error: {exc}")
        finally:
            if stats_file is not None:
                Path(stats_file).unlink(missing_ok=True)
            if use_temp:
                script_path.unlink(missing_ok=True)


async def _run_async_streaming(
    cmd: list[str],
    callback: Callable[[str], None],
    timeout: int = 60,
) -> tuple[int, str]:
    """Run *cmd* as an async subprocess, forwarding each stdout line to *callback*.

    Returns ``(returncode, stderr_text)`` once the process exits (or raises
    ``asyncio.TimeoutError`` if *timeout* seconds elapse).
    """
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def _read_stdout() -> None:
        assert process.stdout is not None
        while True:
            raw = await process.stdout.readline()
            if not raw:
                break
            text = raw.decode("utf-8", errors="replace")
            callback(text.rstrip("\n"))

    await asyncio.wait_for(_read_stdout(), timeout=timeout)
    await process.wait()
    stderr_raw = b""
    if process.stderr is not None:
        stderr_raw = await process.stderr.read()
    return process.returncode or 0, stderr_raw.decode("utf-8", errors="replace")
