"""Shell command context provider."""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from .base import ContextProvider


class CommandContextProvider(ContextProvider):
    """Runs a shell command and injects its stdout as context."""

    def __init__(
        self,
        name: str,
        command: str,
        cwd: Path | None = None,
        timeout: int = 10,
        priority: int = 50,
        max_tokens: int = 2000,
    ) -> None:
        super().__init__(name, priority, max_tokens)
        self._command = command
        self._cwd = cwd or Path.cwd()
        self._timeout = timeout

    @property
    def command(self) -> str:
        return self._command

    async def fetch(self) -> str:
        try:
            result = subprocess.run(
                self._command,
                shell=True,
                cwd=self._cwd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return f"[command timed out after {self._timeout}s]"
        except OSError as exc:
            return f"[command failed: {exc}]"
