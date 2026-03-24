"""Live terminal output capture with context injection support."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass


@dataclass
class CaptureResult:
    """Result of a terminal command capture."""

    command: str
    stdout: str
    stderr: str
    returncode: int
    elapsed_s: float
    # B11: distinguish timeout from other non-zero exit codes
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def combined_output(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)


class TerminalCapture:
    """Run subprocess commands and capture output for LLM context injection.

    Devin 2.0 terminal context parity — captures stdout/stderr with
    timeout enforcement and output size limits.
    """

    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_BYTES = 65536  # 64 KB

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_output_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self.timeout = timeout
        self.max_output_bytes = max_output_bytes

    def run(self, command: str, timeout: int | None = None) -> CaptureResult:
        """Run *command* in a shell and return a CaptureResult.

        stdout and stderr are captured separately and truncated to
        *max_output_bytes* each if necessary.
        """
        effective_timeout = timeout if timeout is not None else self.timeout
        start = time.monotonic()
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
            elapsed = time.monotonic() - start
            stdout = self._truncate(proc.stdout)
            stderr = self._truncate(proc.stderr)
            return CaptureResult(
                command=command,
                stdout=stdout,
                stderr=stderr,
                returncode=proc.returncode,
                elapsed_s=round(elapsed, 3),
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return CaptureResult(
                command=command,
                stdout="",
                stderr=f"[timeout after {effective_timeout}s]",
                returncode=-1,
                elapsed_s=round(elapsed, 3),
                timed_out=True,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - start
            return CaptureResult(
                command=command,
                stdout="",
                stderr=f"[error: {exc}]",
                returncode=-1,
                elapsed_s=round(elapsed, 3),
            )

    def format_for_context(self, result: CaptureResult) -> str:
        """Return a formatted string suitable for LLM system-prompt injection."""
        lines = [
            f"## Terminal output: `{result.command}`",
            f"Exit code: {result.returncode} | Elapsed: {result.elapsed_s}s",
        ]
        if result.stdout:
            lines.append("### stdout")
            lines.append(f"```\n{result.stdout}\n```")
        if result.stderr:
            lines.append("### stderr")
            lines.append(f"```\n{result.stderr}\n```")
        return "\n".join(lines)

    def run_and_format(
        self, command: str, timeout: int | None = None
    ) -> tuple[CaptureResult, str]:
        """Convenience: run *command* and return (CaptureResult, formatted_context)."""
        result = self.run(command, timeout=timeout)
        return result, self.format_for_context(result)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _truncate(self, text: str) -> str:
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= self.max_output_bytes:
            return text
        truncated = encoded[: self.max_output_bytes].decode("utf-8", errors="replace")
        return truncated + f"\n[... truncated at {self.max_output_bytes} bytes]"
