"""Code runner tool — execute Python, Bash, or JS snippets in the REPL."""

from __future__ import annotations

import asyncio
import io
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


@dataclass(frozen=True)
class RunResult:
    """Result of a code execution."""

    stdout: str
    stderr: str
    returncode: int
    elapsed: float
    language: str


class CodeRunner:
    """Execute code snippets in Python, Bash, or JavaScript."""

    def run_python(self, code: str, timeout: int = 30) -> RunResult:
        """Execute Python code in an isolated namespace, capturing stdout/stderr."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        namespace: dict = {"__builtins__": __builtins__}
        start = time.monotonic()
        returncode = 0
        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(compile(code, "<repl>", "exec"), namespace)  # noqa: S102
        except SystemExit as exc:
            returncode = exc.code if isinstance(exc.code, int) else 1
        except Exception as exc:
            import traceback
            stderr_buf.write(traceback.format_exc())
            returncode = 1
        elapsed = time.monotonic() - start
        return RunResult(
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
            returncode=returncode,
            elapsed=elapsed,
            language="python",
        )

    def run_bash(self, command: str, timeout: int = 30) -> RunResult:
        """Run a bash command via subprocess."""
        import subprocess
        start = time.monotonic()
        try:
            proc = subprocess.run(
                command,
                shell=True,  # noqa: S602
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.monotonic() - start
            return RunResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
                elapsed=elapsed,
                language="bash",
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return RunResult(
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                returncode=124,
                elapsed=elapsed,
                language="bash",
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            return RunResult(
                stdout="",
                stderr=str(exc),
                returncode=1,
                elapsed=elapsed,
                language="bash",
            )

    def run_js(self, code: str, timeout: int = 30) -> RunResult:
        """Execute JavaScript via `node -e ...` if node is available."""
        import shutil
        import subprocess

        if not shutil.which("node"):
            return RunResult(
                stdout="",
                stderr="node not found in PATH",
                returncode=127,
                elapsed=0.0,
                language="js",
            )

        start = time.monotonic()
        try:
            proc = subprocess.run(
                ["node", "-e", code],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.monotonic() - start
            return RunResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
                elapsed=elapsed,
                language="js",
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return RunResult(
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                returncode=124,
                elapsed=elapsed,
                language="js",
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            return RunResult(
                stdout="",
                stderr=str(exc),
                returncode=1,
                elapsed=elapsed,
                language="js",
            )


class CodeRunnerTool(BaseTool):
    """Tool: execute Python, Bash, or JS code snippets."""

    @property
    def name(self) -> str:
        return "code_runner"

    @property
    def description(self) -> str:
        return (
            "Execute a code snippet in Python, Bash, or JavaScript. "
            "Returns stdout, stderr, and exit code."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="language",
                type="string",
                description="Language: python, bash, or js",
                enum=["python", "bash", "js"],
            ),
            ToolParameter(
                name="code",
                type="string",
                description="The code to execute",
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Execution timeout in seconds (default 30)",
                required=False,
                default=30,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(self, **kwargs) -> ToolResult:
        language = kwargs.get("language", "python")
        code = kwargs.get("code", "")
        timeout = int(kwargs.get("timeout", 30))

        runner = CodeRunner()
        if language == "python":
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: runner.run_python(code, timeout)
            )
        elif language == "bash":
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: runner.run_bash(code, timeout)
            )
        elif language == "js":
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: runner.run_js(code, timeout)
            )
        else:
            return ToolResult(output=f"Unknown language: {language}", success=False)

        parts = []
        if result.stdout:
            parts.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            parts.append(f"STDERR:\n{result.stderr}")
        parts.append(f"Exit code: {result.returncode} | Elapsed: {result.elapsed:.2f}s")
        output = "\n".join(parts)
        return ToolResult(output=output, success=(result.returncode == 0))
