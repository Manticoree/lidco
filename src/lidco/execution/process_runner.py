"""
Process Runner — execute shell commands with full control over stdin/stdout/stderr.

Features:
- Run commands with timeout, environment variables, working directory
- Pipe commands (command A | command B)
- Stream output line-by-line via callback
- Run multi-line shell scripts
- Capture output as string or stream to callback

Stdlib only (subprocess, threading, os).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ProcessResult:
    """Result of a completed process run."""
    cmd: str | list[str]
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: float
    timed_out: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def output(self) -> str:
        """Combined stdout + stderr."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)

    def format_summary(self) -> str:
        icon = "✓" if self.ok else "✗"
        cmd_str = self.cmd if isinstance(self.cmd, str) else " ".join(str(c) for c in self.cmd)
        lines = [f"{icon} {cmd_str} (exit={self.returncode}, {self.elapsed_ms:.0f}ms)"]
        if self.timed_out:
            lines.append("  [TIMED OUT]")
        if self.stdout:
            lines.append(self.stdout.rstrip())
        if self.stderr:
            lines.append(f"[stderr] {self.stderr.rstrip()}")
        if self.error:
            lines.append(f"[error] {self.error}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# ProcessRunner
# ---------------------------------------------------------------------------

class ProcessRunner:
    """
    Run shell commands and capture output.

    Parameters
    ----------
    default_timeout : float | None
        Default timeout in seconds. None = no timeout.
    default_cwd : str | None
        Default working directory. None = current directory.
    default_env : dict[str, str] | None
        Environment variables merged with current environment.
    shell : bool
        If True, run commands through the system shell (sh/cmd.exe).
    encoding : str
        Text encoding for stdout/stderr.
    """

    def __init__(
        self,
        default_timeout: float | None = 60.0,
        default_cwd: str | None = None,
        default_env: dict[str, str] | None = None,
        shell: bool = True,
        encoding: str = "utf-8",
    ) -> None:
        self._timeout = default_timeout
        self._cwd = default_cwd
        self._env = default_env
        self._shell = shell
        self._encoding = encoding

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        cmd: str | list[str],
        *,
        timeout: float | None = ...,  # type: ignore[assignment]
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        stdin: str | None = None,
        on_output: Callable[[str], None] | None = None,
        shell: bool | None = None,
    ) -> ProcessResult:
        """
        Run a command and return its result.

        Parameters
        ----------
        cmd : str | list[str]
            Command to execute.
        timeout : float | None
            Override default timeout. None = no timeout.
        cwd : str | None
            Working directory for this run.
        env : dict[str, str] | None
            Extra environment variables (merged with default_env + os.environ).
        stdin : str | None
            Text to pipe into the process's stdin.
        on_output : Callable[[str], None] | None
            Callback called for each line of output as it arrives.
        shell : bool | None
            Override default shell setting.
        """
        effective_timeout: float | None = self._timeout if timeout is ... else timeout
        effective_cwd = cwd or self._cwd
        effective_shell = self._shell if shell is None else shell

        # Build env
        effective_env = {**os.environ}
        if self._env:
            effective_env.update(self._env)
        if env:
            effective_env.update(env)

        cmd_str = cmd if isinstance(cmd, str) else " ".join(str(c) for c in cmd)
        start = time.monotonic()

        try:
            stdin_input = stdin.encode(self._encoding) if stdin else None
            proc = subprocess.Popen(
                cmd if effective_shell else (cmd if isinstance(cmd, list) else cmd.split()),
                shell=effective_shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE if stdin else None,
                cwd=effective_cwd,
                env=effective_env,
            )

            if on_output:
                stdout_lines: list[str] = []
                stderr_lines: list[str] = []

                def _read_stdout():
                    assert proc.stdout is not None
                    for raw in proc.stdout:
                        line = raw.decode(self._encoding, errors="replace").rstrip("\n")
                        stdout_lines.append(line)
                        on_output(line)

                def _read_stderr():
                    assert proc.stderr is not None
                    for raw in proc.stderr:
                        line = raw.decode(self._encoding, errors="replace").rstrip("\n")
                        stderr_lines.append(line)

                t_out = threading.Thread(target=_read_stdout, daemon=True)
                t_err = threading.Thread(target=_read_stderr, daemon=True)
                t_out.start()
                t_err.start()

                if stdin_input and proc.stdin:
                    proc.stdin.write(stdin_input)
                    proc.stdin.close()

                timed_out = False
                try:
                    proc.wait(timeout=effective_timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    timed_out = True

                t_out.join(timeout=2)
                t_err.join(timeout=2)
                elapsed = (time.monotonic() - start) * 1000
                return ProcessResult(
                    cmd=cmd_str,
                    returncode=proc.returncode if proc.returncode is not None else -1,
                    stdout="\n".join(stdout_lines),
                    stderr="\n".join(stderr_lines),
                    elapsed_ms=elapsed,
                    timed_out=timed_out,
                )
            else:
                try:
                    stdout_bytes, stderr_bytes = proc.communicate(
                        input=stdin_input,
                        timeout=effective_timeout,
                    )
                    timed_out = False
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout_bytes, stderr_bytes = proc.communicate()
                    timed_out = True

                elapsed = (time.monotonic() - start) * 1000
                return ProcessResult(
                    cmd=cmd_str,
                    returncode=proc.returncode,
                    stdout=stdout_bytes.decode(self._encoding, errors="replace"),
                    stderr=stderr_bytes.decode(self._encoding, errors="replace"),
                    elapsed_ms=elapsed,
                    timed_out=timed_out,
                )
        except FileNotFoundError as exc:
            elapsed = (time.monotonic() - start) * 1000
            return ProcessResult(
                cmd=cmd_str,
                returncode=-1,
                stdout="",
                stderr="",
                elapsed_ms=elapsed,
                error=f"Command not found: {exc}",
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.monotonic() - start) * 1000
            return ProcessResult(
                cmd=cmd_str,
                returncode=-1,
                stdout="",
                stderr="",
                elapsed_ms=elapsed,
                error=str(exc),
            )

    def run_script(
        self,
        script: str,
        *,
        timeout: float | None = ...,  # type: ignore[assignment]
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessResult:
        """
        Run a multi-line shell script.

        Each non-empty line is run in sequence; execution stops on first failure
        unless a line starts with '-' (ignore errors).
        """
        lines = [ln.strip() for ln in script.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        combined_stdout: list[str] = []
        combined_stderr: list[str] = []
        total_start = time.monotonic()

        for line in lines:
            ignore_error = line.startswith("-")
            cmd = line.lstrip("-").strip()
            result = self.run(cmd, timeout=timeout, cwd=cwd, env=env)
            if result.stdout:
                combined_stdout.append(result.stdout)
            if result.stderr:
                combined_stderr.append(result.stderr)
            if not result.ok and not ignore_error:
                elapsed = (time.monotonic() - total_start) * 1000
                return ProcessResult(
                    cmd=script[:80],
                    returncode=result.returncode,
                    stdout="\n".join(combined_stdout),
                    stderr="\n".join(combined_stderr),
                    elapsed_ms=elapsed,
                    timed_out=result.timed_out,
                    error=result.error,
                )

        elapsed = (time.monotonic() - total_start) * 1000
        return ProcessResult(
            cmd=script[:80],
            returncode=0,
            stdout="\n".join(combined_stdout),
            stderr="\n".join(combined_stderr),
            elapsed_ms=elapsed,
        )

    def which(self, name: str) -> str | None:
        """Return the full path of an executable, or None if not found."""
        import shutil
        return shutil.which(name)

    def is_available(self, name: str) -> bool:
        """Return True if the given command is available in PATH."""
        return self.which(name) is not None
